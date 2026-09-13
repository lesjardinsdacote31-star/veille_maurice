"""Accès Supabase : chargement de la config, dédup, écriture des annonces,
journalisation, garde-fous budgétaires.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID

from supabase import Client, create_client

from . import dedup, normalize
from .extraction import DonneesBrutesAnnonce
from .filtre import Criteres, FourchetteBudget
from .notation import Notation


def creer_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    cle = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, cle)


class Stockage:
    def __init__(self, client: Client):
        self.client = client

    # -- Configuration --------------------------------------------------

    def charger_secteurs(self) -> list[normalize.Secteur]:
        reponse = self.client.table("secteurs").select("*").eq("actif", True).execute()
        return [
            normalize.Secteur(id=row["id"], nom=row["nom"], alias=tuple(row["alias"]))
            for row in reponse.data
        ]

    def charger_criteres(self) -> Criteres:
        reponse = self.client.table("parametres").select("*").eq("cle", "criteres").execute()
        if not reponse.data:
            raise RuntimeError("paramètre 'criteres' absent — lancer scripts/migrer_config_vers_supabase.py")
        valeur = reponse.data[0]["valeur"]
        return Criteres(
            budgets_par_type={
                type_bien: FourchetteBudget(
                    min_roupies=fourchette["min_roupies"], max_roupies=fourchette["max_roupies"]
                )
                for type_bien, fourchette in valeur["budgets_par_type"].items()
            },
            mots_exclus=tuple(valeur["mots_exclus"]),
        )

    def charger_sources_actives(self, type_source: str | None = None) -> list[dict]:
        requete = self.client.table("sources").select("*").eq("active", True)
        if type_source:
            requete = requete.eq("type", type_source)
        return requete.execute().data

    def charger_votes_recents(self, limite: int = 50) -> list[dict]:
        reponse = (
            self.client.table("votes")
            .select("valeur, annonces(titre, resume)")
            .order("cree_le", desc=True)
            .limit(limite)
            .execute()
        )
        resultats = []
        for ligne in reponse.data:
            annonce = ligne.get("annonces") or {}
            resultats.append(
                {
                    "valeur": ligne["valeur"],
                    "titre": annonce.get("titre"),
                    "resume": annonce.get("resume"),
                }
            )
        return resultats

    # -- Déduplication ----------------------------------------------------

    def chercher_doublon(
        self, telephones: list[str], prix_roupies: float | None, titre: str | None, secteur_id: str | None
    ) -> dict | None:
        """Retourne l'annonce existante jugée doublon, ou None."""
        cle = dedup.construire_cle_dedup(telephones)

        if cle is not None:
            reponse = self.client.table("annonces").select("*").eq("cle_dedup", cle).execute()
            for existante in reponse.data:
                if dedup.prix_dans_tolerance(prix_roupies, existante.get("prix_roupies")):
                    return existante
            return None

        # Repli par similarité de texte, uniquement si on a de quoi comparer.
        if titre and secteur_id and prix_roupies is not None:
            reponse = self.client.rpc(
                "rechercher_doublons_par_similarite",
                {"p_titre": titre, "p_secteur_id": secteur_id, "p_prix": prix_roupies},
            ).execute()
            if reponse.data:
                return reponse.data[0]

        return None

    # -- Écriture -----------------------------------------------------------

    def enregistrer_annonce(
        self,
        *,
        source_id: str,
        donnees: DonneesBrutesAnnonce,
        secteur_id: str | None,
        notation: Notation | None,
        mode_test: bool,
    ) -> dict:
        doublon = self.chercher_doublon(
            donnees.telephones, donnees.prix_roupies, donnees.titre, secteur_id
        )

        enregistrement = {
            "source_id": source_id,
            "url": donnees.url,
            "titre": donnees.titre,
            "description_brute": donnees.texte_complet[:10000],
            "prix_roupies": donnees.prix_roupies,
            "secteur_id": secteur_id,
            "localisation_texte": donnees.localisation_texte,
            "type_bien": donnees.type_bien,
            "chambres": donnees.chambres,
            "surface_terrain_perches": donnees.surface_terrain_perches,
            "surface_batie_m2": donnees.surface_batie_m2,
            "telephones": donnees.telephones,
            "photos": donnees.photos,
            "cle_dedup": dedup.construire_cle_dedup(donnees.telephones),
            "groupe_dedup_id": doublon["groupe_dedup_id"] if doublon else None,
        }

        if notation is not None:
            enregistrement.update(
                {
                    "score": notation.score,
                    "resume": notation.resume,
                    "drapeaux": notation.drapeaux,
                    "vendeur_type": notation.vendeur_type,
                    "distance_plage_estimee_km": notation.distance_plage_estimee_km,
                }
            )
            if notation.localisation_precise:
                enregistrement["localisation_texte"] = notation.localisation_precise

        if doublon is not None:
            enregistrement["groupe_dedup_id"] = doublon.get("groupe_dedup_id") or doublon["id"]

        if mode_test:
            return {**enregistrement, "id": None, "doublon_de": doublon["id"] if doublon else None}

        reponse = (
            self.client.table("annonces")
            .upsert(enregistrement, on_conflict="source_id,url")
            .execute()
        )
        return reponse.data[0]

    def enregistrer_acteur(self, telephone: str, *, filtree: bool, mode_test: bool) -> None:
        if mode_test:
            return
        existant = (
            self.client.table("acteurs").select("*").eq("telephone_normalise", telephone).execute()
        )
        maintenant = datetime.now(timezone.utc).isoformat()
        if existant.data:
            acteur = existant.data[0]
            self.client.table("acteurs").update(
                {
                    "nb_occurrences": acteur["nb_occurrences"] + 1,
                    "nb_annonces_filtrees": acteur["nb_annonces_filtrees"] + (1 if filtree else 0),
                    "derniere_vue": maintenant,
                }
            ).eq("id", acteur["id"]).execute()
        else:
            self.client.table("acteurs").insert(
                {
                    "telephone_normalise": telephone,
                    "nb_occurrences": 1,
                    "nb_annonces_filtrees": 1 if filtree else 0,
                }
            ).execute()

    # -- Journal & santé des sources -----------------------------------------

    def journaliser(
        self,
        execution_id: str,
        *,
        source_id: str | None,
        niveau: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.client.table("journal").insert(
            {
                "execution_id": execution_id,
                "source_id": source_id,
                "niveau": niveau,
                "message": message,
                "details": details or {},
            }
        ).execute()

    def maj_sante_source(self, source_id: str, *, ok: bool, nb_resultats: int, mode_test: bool) -> None:
        if mode_test:
            return
        source = self.client.table("sources").select("echecs_consecutifs").eq("id", source_id).execute()
        echecs_actuels = source.data[0]["echecs_consecutifs"] if source.data else 0
        self.client.table("sources").update(
            {
                "derniere_collecte_le": datetime.now(timezone.utc).isoformat(),
                "derniere_collecte_ok": ok,
                "derniere_collecte_nb_resultats": nb_resultats,
                "echecs_consecutifs": 0 if ok else echecs_actuels + 1,
            }
        ).eq("id", source_id).execute()

    # -- Compteurs d'usage (garde-fous budgétaires) --------------------------

    def consommer_quota(self, service: str, periode: str, plafond: int, montant: int = 1) -> bool:
        """Retourne True si la consommation est acceptée (sous le plafond)."""
        reponse = self.client.rpc(
            "incrementer_compteur_usage",
            {"p_service": service, "p_periode": periode, "p_plafond": plafond, "p_montant": montant},
        ).execute()
        return bool(reponse.data)
