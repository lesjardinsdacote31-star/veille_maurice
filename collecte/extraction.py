"""Extraction des données d'annonce depuis le HTML brut d'une page.

Trois couches, de la plus fiable à la plus tolérante :
1. JSON-LD schema.org (la plupart des sites mauriciens en exposent)
2. Balises OpenGraph + heuristiques sur le texte visible
3. Gemini Flash en dernier repli (texte brut -> JSON structuré) — c'est ce
   qui permet d'ajouter un petit site sans écrire de parseur dédié.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from . import normalize
from .gemini_client import ClientGemini

TYPES_JSON_LD_PERTINENTS = {
    "Product",
    "Offer",
    "RealEstateListing",
    "House",
    "SingleFamilyResidence",
    "Residence",
    "Place",
}

SCHEMA_EXTRACTION_GEMINI = {
    "type": "object",
    "properties": {
        "titre": {"type": "string"},
        "prix_roupies": {"type": "number"},
        "localisation_texte": {"type": "string"},
        "chambres": {"type": "integer"},
        "surface_terrain_perches": {"type": "number"},
        "type_bien": {"type": "string", "enum": ["maison", "terrain", "autre"]},
        "telephones": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titre"],
}


@dataclass
class DonneesBrutesAnnonce:
    url: str
    titre: str | None = None
    texte_complet: str = ""  # titre + description + OCR : sert au filtre dur et à Gemini
    prix_roupies: float | None = None
    photos: list[str] = field(default_factory=list)
    telephones: list[str] = field(default_factory=list)
    surface_terrain_perches: float | None = None
    surface_batie_m2: float | None = None
    chambres: int | None = None
    localisation_texte: str | None = None
    type_bien: str | None = None
    couche_utilisee: str = "aucune"  # 'json_ld' | 'opengraph' | 'gemini'


def _extraire_blocs_json_ld(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    blocs: list[dict] = []
    for balise in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(balise.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        blocs.extend(data if isinstance(data, list) else [data])
    return blocs


def _prix_depuis_offre(offres) -> float | None:
    if isinstance(offres, list):
        offres = offres[0] if offres else {}
    if not isinstance(offres, dict):
        return None
    prix = offres.get("price") or offres.get("priceSpecification", {}).get("price")
    if prix is None:
        return None
    try:
        return float(prix)
    except (TypeError, ValueError):
        return normalize.normaliser_prix(str(prix))


def _images_depuis_champ(image) -> list[str]:
    if image is None:
        return []
    if isinstance(image, str):
        return [image]
    if isinstance(image, dict):
        url = image.get("url")
        return [url] if url else []
    if isinstance(image, list):
        resultat = []
        for item in image:
            resultat.extend(_images_depuis_champ(item))
        return resultat
    return []


def _depuis_json_ld(html: str) -> DonneesBrutesAnnonce | None:
    for bloc in _extraire_blocs_json_ld(html):
        types = bloc.get("@type")
        types = types if isinstance(types, list) else [types]
        if not any(t in TYPES_JSON_LD_PERTINENTS for t in types if t):
            continue

        titre = bloc.get("name")
        description = bloc.get("description") or ""
        texte_complet = f"{titre or ''}\n{description}"

        chambres_brut = bloc.get("numberOfRooms") or bloc.get("numberOfBedroomsTotal")
        try:
            chambres = int(chambres_brut) if chambres_brut is not None else None
        except (TypeError, ValueError):
            chambres = None

        return DonneesBrutesAnnonce(
            url=bloc.get("url", ""),
            titre=titre,
            texte_complet=texte_complet,
            prix_roupies=_prix_depuis_offre(bloc.get("offers")),
            photos=_images_depuis_champ(bloc.get("image")),
            telephones=normalize.normaliser_telephone(texte_complet),
            surface_terrain_perches=normalize.normaliser_perches(texte_complet),
            chambres=chambres or normalize.normaliser_chambres(texte_complet),
            couche_utilisee="json_ld",
        )
    return None


def _extraire_opengraph(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    og: dict[str, str] = {}
    for balise in soup.find_all("meta"):
        prop = balise.get("property") or balise.get("name") or ""
        if prop.startswith("og:") and balise.get("content"):
            og[prop[3:]] = balise["content"]
    return og


def _texte_visible(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for balise in soup(["script", "style", "nav", "footer", "header"]):
        balise.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def _depuis_opengraph_et_heuristiques(html: str, url: str) -> DonneesBrutesAnnonce:
    og = _extraire_opengraph(html)
    texte_page = _texte_visible(html)
    texte_complet = f"{og.get('title', '')}\n{og.get('description', '')}\n{texte_page}"

    # Les numéros de téléphone/WhatsApp sont souvent injectés dans des
    # attributs HTML (ex: data-whatsappsend="230...", href="tel:...") et pas
    # dans le texte visible : on les cherche donc aussi dans le HTML brut,
    # en plus du texte de la page. Le prix, lui, reste cherché uniquement
    # dans le texte visible pour éviter les faux positifs (ID, hash CSS...).
    telephones = normalize.normaliser_telephone(f"{texte_complet}\n{html}")

    return DonneesBrutesAnnonce(
        url=url,
        titre=og.get("title"),
        texte_complet=texte_complet,
        prix_roupies=normalize.normaliser_prix(texte_complet),
        photos=[og["image"]] if og.get("image") else [],
        telephones=telephones,
        surface_terrain_perches=normalize.normaliser_perches(texte_complet),
        chambres=normalize.normaliser_chambres(texte_complet),
        couche_utilisee="opengraph",
    )


def _donnees_suffisantes(donnees: DonneesBrutesAnnonce) -> bool:
    """Une extraction est jugée suffisante si titre + prix sont présents.

    En dessous, on tente le repli Gemini plutôt que de garder une annonce
    à moitié vide.
    """
    return bool(donnees.titre) and donnees.prix_roupies is not None


def _depuis_gemini(
    client: ClientGemini, texte_brut: str, url: str
) -> DonneesBrutesAnnonce:
    prompt = (
        "Tu extrais les informations d'une annonce immobilière mauricienne "
        "à partir du texte brut d'une page web. Réponds uniquement avec le "
        "JSON demandé, en laissant un champ vide/null si l'information est "
        "absente. Les prix sont en roupies mauriciennes (Rs).\n\n"
        f"Texte brut de la page :\n{texte_brut[:8000]}"
    )
    resultat = client.generer_json(prompt, schema=SCHEMA_EXTRACTION_GEMINI)

    return DonneesBrutesAnnonce(
        url=url,
        titre=resultat.get("titre"),
        texte_complet=texte_brut,
        prix_roupies=resultat.get("prix_roupies"),
        telephones=resultat.get("telephones") or normalize.normaliser_telephone(texte_brut),
        surface_terrain_perches=resultat.get("surface_terrain_perches"),
        chambres=resultat.get("chambres"),
        localisation_texte=resultat.get("localisation_texte"),
        type_bien=resultat.get("type_bien"),
        couche_utilisee="gemini",
    )


def extraire_annonce(
    html: str, url: str, *, client_gemini: ClientGemini | None = None
) -> DonneesBrutesAnnonce:
    """Point d'entrée unique : tente JSON-LD, puis OpenGraph/heuristiques,
    puis Gemini si les deux premières couches sont insuffisantes et qu'un
    client Gemini est fourni (absent en mode test hors-ligne).
    """
    donnees = _depuis_json_ld(html)
    if donnees is not None and _donnees_suffisantes(donnees):
        donnees.url = donnees.url or url
        return donnees

    donnees_og = _depuis_opengraph_et_heuristiques(html, url)
    if _donnees_suffisantes(donnees_og):
        return donnees_og

    if client_gemini is not None:
        return _depuis_gemini(client_gemini, _texte_visible(html), url)

    # Pas de client Gemini disponible (mode test) : on retourne le meilleur
    # résultat obtenu, même incomplet, plutôt que d'échouer.
    return donnees_og
