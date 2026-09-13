"""Filtre dur (sans IA) appliqué avant l'appel à Gemini.

Élimine l'essentiel du volume hors-critères à coût nul : type de bien,
budget (par type — un terrain et une maison n'ont pas la même fourchette),
secteur, mots exclus (locations, PDS/IRS/RES, ventes sur plan). Gemini
n'est appelé que sur ce qui survit à ce filtre.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FourchetteBudget:
    min_roupies: float
    max_roupies: float


@dataclass(frozen=True)
class Criteres:
    # Une fourchette de budget par type de bien accepté (ex: "terrain" et
    # "maison" n'ont pas le même budget) — configurable en base sans
    # toucher au code, voir parametres.criteres dans Supabase.
    budgets_par_type: dict[str, FourchetteBudget]
    mots_exclus: tuple[str, ...]

    @property
    def types_acceptes(self) -> tuple[str, ...]:
        return tuple(self.budgets_par_type.keys())


@dataclass(frozen=True)
class ResultatFiltre:
    retenue: bool
    raison_rejet: str | None = None


def filtrer(
    *,
    texte_complet: str,
    prix_roupies: float | None,
    secteur_id: str | None,
    type_bien: str | None,
    criteres: Criteres,
) -> ResultatFiltre:
    """Applique le filtre dur. `texte_complet` = titre + description (ciblée,
    pas la page entière — voir extraction.description_courte) + OCR des photos.
    """

    texte_bas = (texte_complet or "").lower()

    for mot in criteres.mots_exclus:
        # Limites de mots : un mot court comme "res" (PDS/IRS/RES) ne doit
        # matcher que le mot isolé "res", pas n'importe quel mot qui le
        # contient (ex: "residential", omniprésent dans l'immobilier).
        motif = r"\b" + re.escape(mot.lower()) + r"\b"
        if re.search(motif, texte_bas):
            return ResultatFiltre(False, f"mot_exclu:{mot}")

    if secteur_id is None:
        return ResultatFiltre(False, "secteur_non_detecte")

    if type_bien is None:
        return ResultatFiltre(False, "type_bien_non_detecte")

    fourchette = criteres.budgets_par_type.get(type_bien)
    if fourchette is None:
        return ResultatFiltre(False, "type_bien_non_accepte")

    if prix_roupies is None:
        return ResultatFiltre(False, "prix_non_detecte")

    if prix_roupies < fourchette.min_roupies:
        return ResultatFiltre(False, "prix_sous_budget")

    if prix_roupies > fourchette.max_roupies:
        return ResultatFiltre(False, "prix_au_dessus_budget")

    return ResultatFiltre(True)
