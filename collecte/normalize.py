"""Normalisation des données brutes extraites des annonces.

Ce module concentre la logique la plus sensible du pipeline : parsing des
prix en roupies, des surfaces en perches, des numéros de téléphone
mauriciens, et détection du secteur par alias. Chaque fonction est pure
(aucun accès réseau/DB) pour rester facilement testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 1 perche mauricienne ≈ 42,15 m² (valeur communément admise dans
# l'immobilier local ; "toise" est utilisé comme synonyme de "perche").
M2_PAR_PERCHE = 42.15

_MOTIF_TELEPHONE_BRUT = re.compile(r"(?:\+?230[\s.-]?)?(\d[\d\s.-]{6,12}\d)")


def _telephones_avec_positions(texte: str) -> list[tuple[int, int, str]]:
    """Repère les numéros mauriciens valides et leur position dans le texte.

    Un numéro valide compte 8 chiffres locaux et commence par 5 (mobile),
    ou 6/8/9 (fixe/VoIP). Utilisé à la fois par normaliser_telephone() et
    par normaliser_prix() (pour ne pas confondre un numéro à 8 chiffres
    avec un prix du même ordre de grandeur, ex: 59497477 ~ 59 millions).
    """
    resultats: list[tuple[int, int, str]] = []
    for match in _MOTIF_TELEPHONE_BRUT.finditer(texte):
        brut = match.group(1)
        chiffres = re.sub(r"\D", "", brut)

        if chiffres.startswith("230") and len(chiffres) == 11:
            chiffres = chiffres[3:]

        if len(chiffres) != 8 or chiffres[0] not in "5896":
            continue

        resultats.append((match.start(), match.end(), f"230{chiffres}"))
    return resultats


def normaliser_telephone(texte: str) -> list[str]:
    """Extrait tous les numéros mauriciens d'un texte, au format 230XXXXXXXX.

    Gère : "59497477", "5949 7477", "+230 5492 4746", "230 57850774",
    "Tel:59155845", "WhatsApp: 57067541, 52521797".
    """
    if not texte:
        return []

    trouves: list[str] = []
    for _, _, numero in _telephones_avec_positions(texte):
        if numero not in trouves:
            trouves.append(numero)
    return trouves


def normaliser_prix(texte: str) -> float | None:
    """Extrait un prix en roupies mauriciennes à partir d'un texte libre.

    Gère : "Rs 24,500,000", "2.7m", "4 million", "2,125,000", "10.9M (Neg.)",
    "Prix Rs25000", "2.6 Million per Lot". Retourne None si rien d'exploitable.

    Les séquences reconnues comme numéros de téléphone sont masquées avant
    la recherche de repli "nombre brut", pour éviter qu'un numéro à 8
    chiffres (ex: 59497477) ne soit pris pour un prix du même ordre de
    grandeur que le budget ciblé (5-10 millions de roupies).
    """
    if not texte:
        return None

    texte_bas = texte.lower()

    # Cas "X m" / "X million(s)" / "X k" / "X mille" -> multiplicateur explicite,
    # le plus fiable, évalué avant tout masquage.
    motif_multiplicateur = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(millions?|mille|m|k)\b",
        texte_bas,
    )
    if motif_multiplicateur:
        valeur = float(motif_multiplicateur.group(1).replace(",", "."))
        unite = motif_multiplicateur.group(2)
        if unite in ("million", "millions", "m"):
            return valeur * 1_000_000
        if unite in ("mille", "k"):
            return valeur * 1_000

    # Repli "nombre brut" : on masque d'abord les numéros de téléphone détectés.
    texte_masque = texte
    for start, end, _ in sorted(_telephones_avec_positions(texte), reverse=True):
        texte_masque = texte_masque[:start] + " " * (end - start) + texte_masque[end:]

    candidats = re.findall(r"\d{1,3}(?:[,\s]\d{3})+(?:\.\d+)?|\d{4,}", texte_masque)
    if candidats:
        valeurs = []
        for c in candidats:
            nettoye = c.replace(",", "").replace(" ", "")
            try:
                valeurs.append(float(nettoye))
            except ValueError:
                continue
        valeurs_plausibles = [v for v in valeurs if v >= 10_000]
        if valeurs_plausibles:
            return max(valeurs_plausibles)

    return None


def normaliser_perches(texte: str) -> float | None:
    """Extrait une surface en perches (convertit depuis m² si nécessaire).

    Gère : "29.7 perches", "10,9 perches", "462 m² | 10,9 perches"
    (préfère la mention explicite en perches quand les deux sont présentes),
    "1252m²", "97.2 toises".
    """
    if not texte:
        return None

    texte_bas = texte.lower()

    motif_perche = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(perches?|toises?)\b", texte_bas
    )
    if motif_perche:
        return float(motif_perche.group(1).replace(",", "."))

    motif_m2 = re.search(r"(\d+(?:[.,]\d+)?)\s*m\s*2\b|(\d+(?:[.,]\d+)?)\s*m²", texte_bas)
    if motif_m2:
        valeur_brute = motif_m2.group(1) or motif_m2.group(2)
        m2 = float(valeur_brute.replace(",", "."))
        return round(m2 / M2_PAR_PERCHE, 2)

    return None


def normaliser_chambres(texte: str) -> int | None:
    """Extrait un nombre de chambres. Gère "3 Bedrooms", "3 chambres", "3ch"."""
    if not texte:
        return None

    motif = re.search(
        r"(\d+)\s*(chambres?|bedrooms?|ch\b|bhk)", texte.lower()
    )
    if motif:
        return int(motif.group(1))
    return None


@dataclass(frozen=True)
class Secteur:
    id: str
    nom: str
    alias: tuple[str, ...]


def detecter_secteur(texte: str, secteurs: list[Secteur]) -> str | None:
    """Détecte le secteur mentionné dans le texte via la liste d'alias.

    En cas d'alias multiples correspondants, retient l'alias le plus long
    (le plus spécifique) pour éviter qu'un alias court comme "grand bay"
    ne masque un match plus précis.
    """
    if not texte:
        return None

    texte_bas = texte.lower()
    meilleur: tuple[int, str] | None = None  # (longueur_alias, secteur_id)

    for secteur in secteurs:
        for alias in secteur.alias:
            if alias.lower() in texte_bas:
                if meilleur is None or len(alias) > meilleur[0]:
                    meilleur = (len(alias), secteur.id)

    return meilleur[1] if meilleur else None
