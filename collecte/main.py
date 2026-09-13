"""Orchestrateur de la collecte : sites web + Facebook (pages et groupes).

Usage :
    python -m collecte.main            # collecte réelle : note et écrit en base
    python -m collecte.main --test     # mode test : collecte et note, n'écrit rien,
                                        # n'envoie aucune notification

La collecte est idempotente par conception (upsert sur source_id+url, clé
de dédup téléphone+prix) : un run manqué ou interrompu se rattrape tout
seul au run suivant, sans mécanisme de rattrapage dédié.
"""
from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from . import filtre, frequence, normalize, sources_facebook, sources_sites
from .apify_client import ClientApify, ErreurApify
from .extraction import DonneesBrutesAnnonce
from .gemini_client import ClientGemini, ErreurGemini
from .journal import Journal
from .notation import noter_annonce
from .stockage import Stockage, creer_client

TIMEOUT_HTTP_SECONDES = 20.0

# Plafond mensuel de posts Facebook consommés via Apify, tous types
# confondus (pages + groupes). $5 gratuits / mois ÷ ~$2-3 pour 1000 posts
# ≈ 1900 posts ; on garde une marge de sécurité large plutôt que de viser
# la limite exacte — à ajuster une fois le coût réel observé (tableau de
# bord Apify, ou futur écran M5).
PLAFOND_APIFY_POSTS_MENSUEL = 1200


def _construire_texte_annonce(donnees: DonneesBrutesAnnonce) -> str:
    """Texte utilisé pour la détection de secteur et le filtre dur
    (mots exclus). Volontairement restreint au titre + description ciblée,
    PAS texte_complet : le texte complet de la page inclut souvent des
    menus/filtres ("PDS/RES", liste de tous les secteurs...) ou des
    annonces voisines ("biens similaires") qui faussent sinon la détection
    avec des données d'une autre annonce que celle visée (cf. journal M1 —
    observé en conditions réelles sur plusieurs sites). Pour un post
    Facebook, description_courte == texte_complet (pas de pollution
    possible sur un post isolé), donc ce n'est pas redondant à vérifier.
    """
    return f"{donnees.titre or ''}\n{donnees.description_courte}"


def traiter_annonces_brutes(
    annonces_brutes: list[DonneesBrutesAnnonce],
    *,
    source: dict,
    client_gemini: ClientGemini | None,
    stockage: Stockage,
    secteurs: list[normalize.Secteur],
    criteres: filtre.Criteres,
    votes_passes: list[dict],
    journal: Journal,
    mode_test: bool,
) -> int:
    """Filtre, note et enregistre une liste d'annonces déjà extraites.
    Partagé entre sites et Facebook — la seule différence entre les deux
    est la façon dont annonces_brutes est produite en amont.
    """
    nb_retenues = 0
    for donnees in annonces_brutes:
        texte_annonce = _construire_texte_annonce(donnees)
        secteur_id = normalize.detecter_secteur(texte_annonce, secteurs)

        # Compte l'acteur même si l'annonce est ensuite filtrée (détection
        # des agents récurrents sur tout ce qui est vu, pas seulement retenu).
        for telephone in donnees.telephones:
            stockage.enregistrer_acteur(telephone, filtree=False, mode_test=mode_test)

        resultat_filtre = filtre.filtrer(
            texte_complet=texte_annonce,
            prix_roupies=donnees.prix_roupies,
            secteur_id=secteur_id,
            type_bien=donnees.type_bien,
            criteres=criteres,
        )
        if not resultat_filtre.retenue:
            for telephone in donnees.telephones:
                stockage.enregistrer_acteur(telephone, filtree=True, mode_test=mode_test)
            continue

        notation = None
        if client_gemini is not None:
            try:
                notation = noter_annonce(client_gemini, donnees, votes_passes, criteres)
            except ErreurGemini as exc:
                journal.avertissement(
                    f"échec de notation Gemini, annonce conservée sans score : {exc}",
                    source_id=source["id"],
                )

        stockage.enregistrer_annonce(
            source_id=source["id"],
            donnees=donnees,
            secteur_id=secteur_id,
            notation=notation,
            mode_test=mode_test,
        )
        nb_retenues += 1

    return nb_retenues


def traiter_site(
    source: dict,
    *,
    http_client: httpx.Client,
    client_gemini: ClientGemini | None,
    stockage: Stockage,
    secteurs: list[normalize.Secteur],
    criteres: filtre.Criteres,
    votes_passes: list[dict],
    journal: Journal,
    mode_test: bool,
) -> int:
    """Traite une source de type site. Retourne le nombre d'annonces retenues.

    N'importe quelle exception est capturée par l'appelant (isolation des
    sources) — cette fonction peut lever en cas d'échec.
    """
    annonces_brutes = sources_sites.collecter_site(
        source, http_client=http_client, client_gemini=client_gemini
    )
    journal.info(f"{len(annonces_brutes)} page(s) d'annonce récupérée(s)", source_id=source["id"])

    return traiter_annonces_brutes(
        annonces_brutes,
        source=source,
        client_gemini=client_gemini,
        stockage=stockage,
        secteurs=secteurs,
        criteres=criteres,
        votes_passes=votes_passes,
        journal=journal,
        mode_test=mode_test,
    )


def traiter_facebook(
    source: dict,
    *,
    client_apify: ClientApify,
    client_gemini: ClientGemini | None,
    stockage: Stockage,
    secteurs: list[normalize.Secteur],
    criteres: filtre.Criteres,
    votes_passes: list[dict],
    journal: Journal,
    mode_test: bool,
    periode: str,
) -> int:
    """Traite une source Facebook (page ou groupe). Retourne le nombre
    d'annonces retenues, ou 0 sans erreur si le budget mensuel est atteint
    (ne doit jamais interrompre la collecte des sites)."""
    autorise = mode_test or stockage.consommer_quota(
        "apify", periode, PLAFOND_APIFY_POSTS_MENSUEL, sources_facebook.RESULTATS_MAX_PAR_PASSAGE
    )
    if not autorise:
        journal.avertissement(
            "plafond Apify mensuel atteint, source ignorée ce passage", source_id=source["id"]
        )
        return 0

    posts = sources_facebook.collecter_facebook(source, client_apify=client_apify)
    journal.info(f"{len(posts)} post(s) récupéré(s)", source_id=source["id"])

    annonces_brutes = [
        donnees
        for post in posts
        if (donnees := sources_facebook.convertir_post(post)) is not None
    ]

    return traiter_annonces_brutes(
        annonces_brutes,
        source=source,
        client_gemini=client_gemini,
        stockage=stockage,
        secteurs=secteurs,
        criteres=criteres,
        votes_passes=votes_passes,
        journal=journal,
        mode_test=mode_test,
    )


def executer(mode_test: bool) -> None:
    load_dotenv()
    execution_id = str(uuid.uuid4())
    maintenant = datetime.now(timezone.utc)
    periode = maintenant.strftime("%Y-%m")

    client_supabase = creer_client()
    stockage = Stockage(client_supabase)
    journal = Journal(stockage, execution_id, mode_test)

    journal.info(f"démarrage de la collecte (mode_test={mode_test})")

    secteurs = stockage.charger_secteurs()
    criteres = stockage.charger_criteres()
    votes_passes = stockage.charger_votes_recents()

    cle_gemini = os.environ.get("GEMINI_API_KEY")
    client_gemini = ClientGemini(cle_api=cle_gemini) if cle_gemini else None
    if client_gemini is None:
        journal.avertissement("GEMINI_API_KEY absente : notation et repli d'extraction désactivés")

    total_retenues = 0

    # -- Sites web ------------------------------------------------------------
    sources_sites_actives = stockage.charger_sources_actives(type_source="site")
    with httpx.Client(timeout=TIMEOUT_HTTP_SECONDES) as http_client:
        for source in sources_sites_actives:
            try:
                nb_retenues = traiter_site(
                    source,
                    http_client=http_client,
                    client_gemini=client_gemini,
                    stockage=stockage,
                    secteurs=secteurs,
                    criteres=criteres,
                    votes_passes=votes_passes,
                    journal=journal,
                    mode_test=mode_test,
                )
                stockage.maj_sante_source(
                    source["id"], ok=True, nb_resultats=nb_retenues, mode_test=mode_test
                )
                journal.info(f"{nb_retenues} annonce(s) retenue(s)", source_id=source["id"])
                total_retenues += nb_retenues
            except Exception as exc:  # noqa: BLE001 — isolation volontaire de la source
                journal.erreur(f"échec de la collecte : {exc}", source_id=source["id"])
                stockage.maj_sante_source(source["id"], ok=False, nb_resultats=0, mode_test=mode_test)

    # -- Facebook (pages puis groupes) -----------------------------------------
    cle_apify = os.environ.get("APIFY_API_TOKEN")
    client_apify = ClientApify(token=cle_apify) if cle_apify else None
    if client_apify is None:
        journal.avertissement("APIFY_API_TOKEN absente : collecte Facebook désactivée")
    else:
        for type_source in ("page_facebook", "groupe_facebook"):
            sources_fb = stockage.charger_sources_actives(type_source=type_source)
            for source in sources_fb:
                if not frequence.est_due(
                    source.get("frequence", "chaque_run"),
                    source.get("derniere_collecte_le"),
                    maintenant=maintenant,
                ):
                    continue
                try:
                    nb_retenues = traiter_facebook(
                        source,
                        client_apify=client_apify,
                        client_gemini=client_gemini,
                        stockage=stockage,
                        secteurs=secteurs,
                        criteres=criteres,
                        votes_passes=votes_passes,
                        journal=journal,
                        mode_test=mode_test,
                        periode=periode,
                    )
                    stockage.maj_sante_source(
                        source["id"], ok=True, nb_resultats=nb_retenues, mode_test=mode_test
                    )
                    journal.info(f"{nb_retenues} annonce(s) retenue(s)", source_id=source["id"])
                    total_retenues += nb_retenues
                except (Exception, ErreurApify) as exc:  # noqa: BLE001 — isolation volontaire
                    journal.erreur(f"échec de la collecte : {exc}", source_id=source["id"])
                    stockage.maj_sante_source(
                        source["id"], ok=False, nb_resultats=0, mode_test=mode_test
                    )

    journal.info(f"collecte terminée : {total_retenues} annonce(s) retenue(s) au total")


def main() -> None:
    analyseur = argparse.ArgumentParser(description="Collecte des sites immobiliers et de Facebook")
    analyseur.add_argument(
        "--test",
        action="store_true",
        help="Mode test : collecte et note sans rien écrire en base ni envoyer de notification",
    )
    args = analyseur.parse_args()
    executer(mode_test=args.test)


if __name__ == "__main__":
    main()
