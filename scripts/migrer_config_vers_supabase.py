"""Migre config/config_initiale.yaml vers Supabase (parametres, secteurs, sources).

À lancer une première fois pour amorcer la base, puis seulement si
config_initiale.yaml est modifié à la main (ajout groupé de sources, par
exemple) — l'usage courant (ajouter une source, l'activer/désactiver) passe
par l'écran d'administration de l'app, pas par ce script.

Usage :
    python -m scripts.migrer_config_vers_supabase
"""
from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv

from collecte.stockage import creer_client

CHEMIN_CONFIG = Path(__file__).parent.parent / "config" / "config_initiale.yaml"


def migrer() -> None:
    load_dotenv()
    config = yaml.safe_load(CHEMIN_CONFIG.read_text(encoding="utf-8"))
    client = creer_client()

    # -- Critères (paramètres globaux) --------------------------------------
    client.table("parametres").upsert(
        {"cle": "criteres", "valeur": config["criteres"]}
    ).execute()
    print("Critères migrés.")

    # -- Secteurs -------------------------------------------------------------
    for secteur in config["secteurs"]:
        client.table("secteurs").upsert(
            {"id": secteur["id"], "nom": secteur["nom"], "alias": secteur["alias"], "actif": True}
        ).execute()
    print(f"{len(config['secteurs'])} secteur(s) migré(s).")

    # -- Sources ---------------------------------------------------------------
    def migrer_sources(cle_config: str, type_source: str) -> int:
        compteur = 0
        for entree in config.get(cle_config, []):
            prive = entree.get("prive", False)
            client.table("sources").upsert(
                {
                    "type": type_source,
                    "identifiant": entree["identifiant"],
                    "nom": entree["nom"],
                    "priorite": entree.get("priorite", 2),
                    "frequence": entree.get("frequence", "chaque_run"),
                    "prive": prive,
                    # Un groupe privé reste inactif tant que l'accès (cookies
                    # + compte dédié) n'est pas mis en place manuellement.
                    "active": not prive,
                },
                on_conflict="type,identifiant",
            ).execute()
            compteur += 1
        return compteur

    nb_sites = migrer_sources("sources_sites", "site")
    print(f"{nb_sites} site(s) migré(s).")

    nb_pages = migrer_sources("sources_pages_facebook", "page_facebook")
    print(f"{nb_pages} page(s) Facebook migrée(s).")

    nb_groupes = migrer_sources("sources_groupes_facebook", "groupe_facebook")
    print(f"{nb_groupes} groupe(s) Facebook migré(s).")


if __name__ == "__main__":
    migrer()
