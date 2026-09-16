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

from . import filtre, frequence, normalize, notifications, sources_facebook, sources_sites
from .apify_client import ClientApify, ErreurApify
from .extraction import DonneesBrutesAnnonce
from .gemini_client import ClientGemini, ErreurGemini
from .journal import Journal
from .notation import noter_annonce
from .stockage import Stockage, creer_client

TIMEOUT_HTTP_SECONDES = 20.0

# Plafond mensuel de LANCEMENTS Apify (pas de posts — mesuré en conditions
# réelles, ~0,076$/lancement quasi indépendamment du nombre de résultats,
# voir README). Sites et groupes sont chacun regroupés en un seul
# lancement par passage Facebook (voir _collecter_type_facebook), donc
# 2 lancements/jour x 30 jours = 60, sous les ~65 que couvrent les 5$
# gratuits mensuels — marge de sécurité volontaire.
PLAFOND_APIFY_LANCEMENTS_MENSUEL = 55


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

        annonce_enregistree = stockage.enregistrer_annonce(
            source_id=source["id"],
            donnees=donnees,
            secteur_id=secteur_id,
            notation=notation,
            mode_test=mode_test,
        )
        nb_retenues += 1

        if annonce_enregistree.get("nouvelle"):
            try:
                nb_envoyees = notifications.notifier_nouvelle_annonce(
                    stockage, annonce_enregistree, mode_test=mode_test
                )
                if not mode_test:
                    journal.info(f"{nb_envoyees} notification(s) envoyée(s)", source_id=source["id"])
            except notifications.ErreurNotification as exc:
                journal.avertissement(f"notification non envoyée : {exc}", source_id=source["id"])

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


def traiter_facebook_groupe(
    sources_dues: list[dict],
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
    """Traite toutes les sources Facebook dues (même type : pages OU
    groupes) en UN SEUL lancement Apify groupé — voir sources_facebook.py
    pour pourquoi le regroupement est indispensable au budget. Met à jour
    la santé de chaque source individuellement malgré le lancement commun.
    Retourne le nombre total d'annonces retenues sur ce lot.
    """
    if not sources_dues:
        return 0

    autorise = stockage.consommer_quota("apify", periode, PLAFOND_APIFY_LANCEMENTS_MENSUEL, 1)
    if not autorise:
        journal.avertissement(
            f"plafond Apify mensuel atteint, {len(sources_dues)} source(s) ignorée(s) ce passage"
        )
        return 0

    try:
        posts_par_source = sources_facebook.collecter_facebook_groupe(
            sources_dues, client_apify=client_apify
        )
    except Exception as exc:  # noqa: BLE001 — un lancement groupé qui échoue ne doit
        # jamais faire tomber le reste de la collecte (sites, autre type Facebook).
        journal.erreur(f"échec du lancement Apify groupé : {exc}")
        for source in sources_dues:
            stockage.maj_sante_source(source["id"], ok=False, nb_resultats=0, mode_test=mode_test)
        return 0

    total_retenues_lot = 0
    for source in sources_dues:
        posts = posts_par_source.get(source["identifiant"], [])
        annonces_brutes = [
            donnees
            for post in posts
            if (donnees := sources_facebook.convertir_post(post)) is not None
        ]
        nb_retenues = traiter_annonces_brutes(
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
        stockage.maj_sante_source(source["id"], ok=True, nb_resultats=nb_retenues, mode_test=mode_test)
        journal.info(
            f"{len(posts)} post(s) récupéré(s), {nb_retenues} annonce(s) retenue(s)",
            source_id=source["id"],
        )
        total_retenues_lot += nb_retenues

    return total_retenues_lot


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

    # -- Facebook (pages puis groupes, chacun en UN lancement Apify groupé) ---
    # Limité à 1 passage/jour (variable COLLECTER_FACEBOOK, positionnée par
    # le workflow uniquement sur le premier cron du jour) : chaque lancement
    # coûte un forfait fixe quasi indépendant du volume — voir README,
    # section budget Facebook, pour l'incident qui a motivé cette décision.
    collecter_facebook_aujourdhui = os.environ.get("COLLECTER_FACEBOOK", "true") == "true"
    cle_apify = os.environ.get("APIFY_API_TOKEN")
    client_apify = ClientApify(token=cle_apify) if cle_apify else None

    if client_apify is None:
        journal.avertissement("APIFY_API_TOKEN absente : collecte Facebook désactivée")
    elif not collecter_facebook_aujourdhui:
        journal.info("collecte Facebook non due aujourd'hui (déjà faite ce jour)")
    else:
        for type_source in ("page_facebook", "groupe_facebook"):
            sources_fb = stockage.charger_sources_actives(type_source=type_source)
            sources_dues = [
                s
                for s in sources_fb
                if frequence.est_due(
                    s.get("frequence", "chaque_run"), s.get("derniere_collecte_le"), maintenant=maintenant
                )
            ]
            if not sources_dues:
                continue
            try:
                total_retenues += traiter_facebook_groupe(
                    sources_dues,
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
            except ErreurApify as exc:  # noqa: BLE001 — isolation volontaire du type Facebook
                journal.erreur(f"échec de la collecte Facebook ({type_source}) : {exc}")

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
