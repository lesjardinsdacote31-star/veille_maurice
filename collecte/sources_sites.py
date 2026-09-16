"""Collecte des annonces depuis les sites web (via requêtes HTTP directes).

Deux étapes par site :
1. Récupérer la page d'index/recherche et en extraire les liens vers des
   pages d'annonce individuelles (heuristique générique, surchageable par
   source via `config_extraction.motif_lien_annonce`, une regex). Si cette
   page n'en révèle aucun (cas fréquent : cartes générées en JavaScript,
   sans lien exploitable dans le HTML brut), repli sur le sitemap XML du
   domaine — souvent statique même quand la page d'index ne l'est pas.
2. Récupérer chaque page d'annonce et l'extraire via extraction.py.

Isolation stricte : une exception sur un site (timeout, blocage anti-bot,
structure imprévue) est capturée et journalisée, jamais propagée — le job
continue sur les sites suivants. Un lien issu du sitemap mais menant en
réalité à une location (le sitemap ne distingue pas toujours vente/location
dans l'URL) n'est pas un problème : le contenu de la page sera rejeté plus
loin par `mots_exclus` (voir filtre.py), qui se base sur le texte, pas l'URL.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .extraction import DonneesBrutesAnnonce, extraire_annonce
from .gemini_client import ClientGemini, ErreurGemini

EN_TETES_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

MOTIF_LIEN_ANNONCE_PAR_DEFAUT = re.compile(
    r"(propert(y|i)|annonce|advert|listing|for-sale|a-vendre|maison|terrain|house|land)"
    r"[-_/].*\d",
    re.IGNORECASE,
)

NB_MAX_ANNONCES_PAR_PASSAGE = 40


class ErreurCollecteSite(RuntimeError):
    pass


def decouvrir_liens_annonces(
    html: str, url_base: str, *, motif_regex: str | None = None
) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    motif = re.compile(motif_regex, re.IGNORECASE) if motif_regex else MOTIF_LIEN_ANNONCE_PAR_DEFAUT

    domaine_base = urlparse(url_base).netloc

    liens: set[str] = set()
    for balise_a in soup.find_all("a", href=True):
        url_absolue = urljoin(url_base, balise_a["href"]).split("#")[0]
        # Restreint au même domaine que la page d'index : évite les boutons
        # de partage (Pinterest, WhatsApp...) qui embarquent l'URL de
        # l'annonce d'origine dans leur propre URL externe et matcheraient
        # sinon le motif ci-dessous par erreur.
        if urlparse(url_absolue).netloc != domaine_base:
            continue
        if motif.search(url_absolue):
            liens.add(url_absolue)

    return list(liens)[:NB_MAX_ANNONCES_PAR_PASSAGE]


def decouvrir_liens_sitemap(
    html_sitemap: str, url_sitemap: str, *, motif_regex: str | None = None
) -> tuple[list[str], list[str]]:
    """Extrait les <loc> d'un sitemap XML, filtrés par le motif de lien
    d'annonce. Retourne aussi les <loc> se terminant par .xml séparément
    (sous-sitemaps d'un sitemap-index), pour permettre un repli en cascade.

    Le standard sitemap exige des URLs absolues, mais certains sites (ex:
    harris-properties.com, vérifié en conditions réelles) publient des <loc>
    relatives — `urljoin` les résout par rapport à l'URL du sitemap lui-même,
    sinon `httpx` échoue purement et simplement dessus.
    """
    motif = re.compile(motif_regex, re.IGNORECASE) if motif_regex else MOTIF_LIEN_ANNONCE_PAR_DEFAUT
    locs = [urljoin(url_sitemap, loc) for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", html_sitemap)]
    sous_sitemaps = [loc for loc in locs if loc.lower().endswith(".xml")]
    liens = [loc for loc in locs if not loc.lower().endswith(".xml") and motif.search(loc)]
    return liens[:NB_MAX_ANNONCES_PAR_PASSAGE], sous_sitemaps


def _liens_via_sitemap(
    http_client: httpx.Client, url_index: str, *, motif_regex: str | None = None
) -> list[str]:
    domaine_racine = f"{urlparse(url_index).scheme}://{urlparse(url_index).netloc}"
    url_sitemap = f"{domaine_racine}/sitemap.xml"
    try:
        reponse = http_client.get(url_sitemap, headers=EN_TETES_HTTP, timeout=15, follow_redirects=True)
        reponse.raise_for_status()
    except httpx.HTTPError:
        return []

    liens, sous_sitemaps = decouvrir_liens_sitemap(reponse.text, str(reponse.url), motif_regex=motif_regex)
    if liens:
        return liens

    # Sitemap-index (le fichier racine ne fait que lister des sous-sitemaps) :
    # on ne suit que le premier sous-sitemap dont le nom évoque l'immobilier,
    # pour rester léger — pas de crawl récursif complet.
    candidat = next((s for s in sous_sitemaps if "propert" in s.lower() or "annonce" in s.lower()), None)
    if not candidat:
        return []
    try:
        reponse2 = http_client.get(candidat, headers=EN_TETES_HTTP, timeout=15, follow_redirects=True)
        reponse2.raise_for_status()
    except httpx.HTTPError:
        return []
    liens, _ = decouvrir_liens_sitemap(reponse2.text, str(reponse2.url), motif_regex=motif_regex)
    return liens


def collecter_site(
    source: dict,
    *,
    http_client: httpx.Client,
    client_gemini: ClientGemini | None,
) -> list[DonneesBrutesAnnonce]:
    """Retourne les annonces extraites pour une source de type 'site'.

    Lève ErreurCollecteSite en cas d'échec — à l'appelant de l'attraper et
    d'isoler l'échec (voir main.py).
    """
    url_index = source["identifiant"]
    motif_lien = (source.get("config_extraction") or {}).get("motif_lien_annonce")

    try:
        reponse_index = http_client.get(url_index, headers=EN_TETES_HTTP, follow_redirects=True)
        reponse_index.raise_for_status()
    except httpx.HTTPError as exc:
        raise ErreurCollecteSite(f"échec de récupération de l'index {url_index} : {exc}") from exc

    liens_annonces = decouvrir_liens_annonces(reponse_index.text, url_index, motif_regex=motif_lien)
    if not liens_annonces:
        liens_annonces = _liens_via_sitemap(http_client, url_index, motif_regex=motif_lien)

    resultats: list[DonneesBrutesAnnonce] = []
    for url_annonce in liens_annonces:
        try:
            reponse = http_client.get(url_annonce, headers=EN_TETES_HTTP, follow_redirects=True)
            reponse.raise_for_status()
        except httpx.HTTPError:
            continue  # une annonce isolée qui échoue ne doit pas arrêter le site

        try:
            donnees = extraire_annonce(reponse.text, url_annonce, client_gemini=client_gemini)
        except ErreurGemini:
            # Le repli Gemini de l'extraction a échoué (ex: surcharge du
            # plan gratuit) : on saute cette annonce, elle sera retentée au
            # prochain passage planifié plutôt que de faire échouer tout le site.
            continue
        resultats.append(donnees)

    return resultats
