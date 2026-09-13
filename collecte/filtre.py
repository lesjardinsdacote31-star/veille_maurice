"""Filtre dur (sans IA) appliqué avant l'appel à Gemini.

Élimine l'essentiel du volume hors-critères à coût nul : budget, secteur,
mots exclus (locations, PDS/IRS/RES, ventes sur plan). Gemini n'est appelé
que sur ce qui survit à ce filtre.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Criteres:
    budget_min_roupies: float
    budget_max_roupies: float
    types_acceptes: tuple[str, ...]
    mots_exclus: tuple[str, ...]


@dataclass(frozen=True)
class ResultatFiltre:
    retenue: bool
    raison_rejet: str | None = None


def filtrer(
    *,
    texte_complet: str,
    prix_roupies: float | None,
    secteur_id: str | None,
    criteres: Criteres,
) -> ResultatFiltre:
    """Applique le filtre dur. `texte_complet` = titre + description + OCR des photos."""

    texte_bas = (texte_complet or "").lower()

    for mot in criteres.mots_exclus:
        if mot.lower() in texte_bas:
            return ResultatFiltre(False, f"mot_exclu:{mot}")

    if secteur_id is None:
        return ResultatFiltre(False, "secteur_non_detecte")

    if prix_roupies is None:
        return ResultatFiltre(False, "prix_non_detecte")

    if prix_roupies < criteres.budget_min_roupies:
        return ResultatFiltre(False, "prix_sous_budget")

    if prix_roupies > criteres.budget_max_roupies:
        return ResultatFiltre(False, "prix_au_dessus_budget")

    return ResultatFiltre(True)
