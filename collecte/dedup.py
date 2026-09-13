"""Détection des doublons entre annonces.

Clé fiable : numéro de téléphone + prix à 3 % près (les agences republient
le même mandat sur plusieurs sites). Repli quand aucun téléphone n'est
détecté : recherche par similarité de texte (pg_trgm), gérée côté
stockage.py car elle nécessite une requête SQL — ce module ne contient que
la logique pure, testable sans base de données.
"""
from __future__ import annotations

from dataclasses import dataclass

TOLERANCE_PRIX_DEFAUT = 0.03
TOLERANCE_SURFACE_DEFAUT = 0.05


def construire_cle_dedup(telephones: list[str]) -> str | None:
    """Construit la clé de dédup primaire à partir du premier téléphone détecté.

    Retourne None si aucun téléphone n'est disponible : le repli par
    similarité de texte prend alors le relais (voir stockage.py).
    """
    if not telephones:
        return None
    return f"tel:{telephones[0]}"


def prix_dans_tolerance(
    prix_a: float | None, prix_b: float | None, tolerance: float = TOLERANCE_PRIX_DEFAUT
) -> bool:
    """True si deux prix sont considérés comme le même bien (écart relatif <= tolérance)."""
    if prix_a is None or prix_b is None:
        return False
    if prix_a == 0 and prix_b == 0:
        return True
    if prix_a == 0 or prix_b == 0:
        return False
    ecart_relatif = abs(prix_a - prix_b) / max(prix_a, prix_b)
    return ecart_relatif <= tolerance


def surface_dans_tolerance(
    surface_a: float | None,
    surface_b: float | None,
    tolerance: float = TOLERANCE_SURFACE_DEFAUT,
) -> bool:
    if surface_a is None or surface_b is None:
        return False
    if surface_a == 0 or surface_b == 0:
        return surface_a == surface_b
    ecart_relatif = abs(surface_a - surface_b) / max(surface_a, surface_b)
    return ecart_relatif <= tolerance


@dataclass(frozen=True)
class AnnoncePourDedup:
    telephones: tuple[str, ...]
    prix_roupies: float | None
    surface_terrain_perches: float | None = None


def sont_probablement_doublons(
    a: AnnoncePourDedup,
    b: AnnoncePourDedup,
    tolerance_prix: float = TOLERANCE_PRIX_DEFAUT,
) -> bool:
    """Décision de dédup par la clé fiable : téléphone commun + prix à 3 % près."""
    telephones_communs = set(a.telephones) & set(b.telephones)
    if not telephones_communs:
        return False
    return prix_dans_tolerance(a.prix_roupies, b.prix_roupies, tolerance_prix)
