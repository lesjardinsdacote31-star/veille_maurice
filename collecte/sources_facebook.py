"""Collecte des annonces depuis Facebook (pages et groupes) via Apify.

Pas de connexion/cookies : les acteurs Apify officiels lisent le contenu
public directement (vérifié en conditions réelles — voir README). Les 3
groupes marqués "prive" en base restent inactifs tant que cette approche
n'est pas mise en place manuellement (compte dédié + cookies).

Regroupement obligatoire : Apify facture ces acteurs un forfait fixe par
LANCEMENT (~0,076$, mesuré en conditions réelles), quasiment indépendant
du nombre de résultats — un lancement par source épuiserait le budget
gratuit en un seul passage. `resultsLimit` s'applique par URL (vérifié en
direct : 2 URLs, resultsLimit=6 -> 6 posts par URL, 12 au total), donc
regrouper N sources dans un seul lancement coûte le même forfait tout en
retournant les mêmes résultats par source qu'un lancement individuel.
Voir README, section budget Facebook, pour l'incident qui a mené à ce
choix.

Le texte d'un post (description_courte = texte_complet) ne souffre pas de
la pollution "page entière" rencontrée sur les sites web : un post Facebook
n'a pas de menu de navigation ni de "biens similaires" mélangés dedans.
"""
from __future__ import annotations

from collections import defaultdict

from . import normalize
from .apify_client import ClientApify
from .extraction import DonneesBrutesAnnonce

ACTEUR_PAGES = "apify/facebook-posts-scraper"
ACTEUR_GROUPES = "apify/facebook-groups-scraper"

RESULTATS_MAX_PAR_PASSAGE = 15


def _acteur_pour(type_source: str) -> str:
    return ACTEUR_PAGES if type_source == "page_facebook" else ACTEUR_GROUPES


def collecter_facebook_groupe(sources: list[dict], *, client_apify: ClientApify) -> dict[str, list[dict]]:
    """Un seul lancement Apify pour plusieurs sources du même type (pages OU
    groupes, pas les deux : elles utilisent des acteurs différents).
    Retourne les posts bruts regroupés par `identifiant` de source.
    """
    if not sources:
        return {}

    type_source = sources[0]["type"]
    entree: dict = {
        "startUrls": [{"url": s["identifiant"]} for s in sources],
        "resultsLimit": RESULTATS_MAX_PAR_PASSAGE,
    }

    # Le filtre de date s'applique à tout le lancement : on prend la plus
    # ancienne date parmi le lot (jamais rater un post neuf sur une source
    # moins souvent vérifiée — un doublon éventuel est absorbé sans dégât
    # par la dédup sur source_id+url).
    dates_connues = [s["derniere_collecte_le"] for s in sources if s.get("derniere_collecte_le")]
    if len(dates_connues) == len(sources):
        entree["onlyPostsNewerThan"] = min(dates_connues)[:10]

    posts = client_apify.executer_acteur(_acteur_pour(type_source), entree)

    par_source: dict[str, list[dict]] = defaultdict(list)
    identifiants_connus = {s["identifiant"] for s in sources}
    for post in posts:
        cle = post.get("facebookUrl") or ""
        if cle in identifiants_connus:
            par_source[cle].append(post)
        # Un post dont l'URL de conteneur ne correspond à aucune source
        # demandée est ignoré (ne devrait pas arriver, mais ne doit pas
        # planter le lot si Apify renvoie un champ inattendu).

    return par_source


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
