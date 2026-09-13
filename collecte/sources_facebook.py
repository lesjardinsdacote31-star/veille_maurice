"""Collecte des annonces depuis Facebook (pages et groupes) via Apify.

Pas de connexion/cookies : les acteurs Apify officiels lisent le contenu
public directement (vérifié en conditions réelles — voir README). Les 3
groupes marqués "prive" en base restent inactifs tant que cette approche
n'est pas mise en place manuellement (compte dédié + cookies).

Le texte d'un post (description_courte = texte_complet) ne souffre pas de
la pollution "page entière" rencontrée sur les sites web : un post Facebook
n'a pas de menu de navigation ni de "biens similaires" mélangés dedans.
"""
from __future__ import annotations

from . import normalize
from .apify_client import ClientApify
from .extraction import DonneesBrutesAnnonce

ACTEUR_PAGES = "apify/facebook-posts-scraper"
ACTEUR_GROUPES = "apify/facebook-groups-scraper"

RESULTATS_MAX_PAR_PASSAGE = 15


def _acteur_pour(type_source: str) -> str:
    return ACTEUR_PAGES if type_source == "page_facebook" else ACTEUR_GROUPES


def collecter_facebook(source: dict, *, client_apify: ClientApify) -> list[dict]:
    """Retourne les posts bruts (dicts Apify) pour une source page/groupe Facebook."""
    entree: dict = {
        "startUrls": [{"url": source["identifiant"]}],
        "resultsLimit": RESULTATS_MAX_PAR_PASSAGE,
    }
    if source.get("derniere_collecte_le"):
        # Ne redemande que les posts publiés depuis le dernier passage réussi
        # sur CETTE source — maîtrise le budget Apify (voir README).
        entree["onlyPostsNewerThan"] = source["derniere_collecte_le"][:10]

    return client_apify.executer_acteur(_acteur_pour(source["type"]), entree)


def _texte_post(post: dict) -> str:
    morceaux = [post.get("text") or ""]
    for piece in post.get("attachments", []) or []:
        if piece.get("ocrText"):
            morceaux.append(piece["ocrText"])
    return "\n".join(m for m in morceaux if m).strip()


def _photos_post(post: dict) -> list[str]:
    photos = []
    for piece in post.get("attachments", []) or []:
        url = piece.get("thumbnail") or (piece.get("image") or {}).get("uri")
        if url:
            photos.append(url)
    return photos


def convertir_post(post: dict) -> DonneesBrutesAnnonce | None:
    """Convertit un post Apify brut en DonneesBrutesAnnonce, via les mêmes
    fonctions de normalisation que pour les sites — un post FB n'a pas de
    "titre" à proprement parler, le début du texte en tient lieu.
    """
    texte = _texte_post(post)
    if not texte:
        return None  # post sans texte ni OCR (juste une photo de profil, un like...)

    url = post.get("url") or post.get("facebookUrl") or post.get("permalink_url") or ""
    titre = texte.splitlines()[0][:120]

    return DonneesBrutesAnnonce(
        url=url,
        titre=titre,
        texte_complet=texte,
        description_courte=texte,
        prix_roupies=normalize.normaliser_prix(texte),
        photos=_photos_post(post),
        telephones=normalize.normaliser_telephone(texte),
        surface_terrain_perches=normalize.normaliser_perches(texte),
        chambres=normalize.normaliser_chambres(texte),
        type_bien=normalize.detecter_type_bien(texte),
        couche_utilisee="facebook",
    )
