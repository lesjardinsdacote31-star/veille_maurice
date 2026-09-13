"""Orchestrateur de la collecte des sites web.

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

import httpx
from dotenv import load_dotenv

from . import filtre, normalize, sources_sites
from .extraction import DonneesBrutesAnnonce
from .gemini_client import ClientGemini, ErreurGemini
from .journal import Journal
from .notation import noter_annonce
from .stockage import Stockage, creer_client

TIMEOUT_HTTP_SECONDES = 20.0


def _construire_texte_annonce(donnees: DonneesBrutesAnnonce) -> str:
    """Texte utilisé pour la détection de secteur et le filtre dur
    (mots exclus). Volontairement restreint au titre + description ciblée,
    PAS texte_complet : le texte complet de la page inclut souvent des
    menus/filtres ("PDS/RES", liste de tous les secteurs...) ou des
    annonces voisines ("biens similaires") qui faussent sinon la détection
    avec des données d'une autre annonce que celle visée (cf. journal M1 —
    observé en conditions réelles sur plusieurs sites).
    """
    return f"{donnees.titre or ''}\n{donnees.description_courte}"


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


def executer(mode_test: bool) -> None:
    load_dotenv()
    execution_id = str(uuid.uuid4())

    client_supabase = creer_client()
    stockage = Stockage(client_supabase)
    journal = Journal(stockage, execution_id, mode_test)

    journal.info(f"démarrage de la collecte (mode_test={mode_test})")

    secteurs = stockage.charger_secteurs()
    criteres = stockage.charger_criteres()
    votes_passes = stockage.charger_votes_recents()
    sources = stockage.charger_sources_actives(type_source="site")

    cle_gemini = os.environ.get("GEMINI_API_KEY")
    client_gemini = ClientGemini(cle_api=cle_gemini) if cle_gemini else None
    if client_gemini is None:
        journal.avertissement("GEMINI_API_KEY absente : notation et repli d'extraction désactivés")

    total_retenues = 0
    with httpx.Client(timeout=TIMEOUT_HTTP_SECONDES) as http_client:
        for source in sources:
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

    journal.info(f"collecte terminée : {total_retenues} annonce(s) retenue(s) au total")


def main() -> None:
    analyseur = argparse.ArgumentParser(description="Collecte des sites immobiliers")
    analyseur.add_argument(
        "--test",
        action="store_true",
        help="Mode test : collecte et note sans rien écrire en base ni envoyer de notification",
    )
    args = analyseur.parse_args()
    executer(mode_test=args.test)


if __name__ == "__main__":
    main()
