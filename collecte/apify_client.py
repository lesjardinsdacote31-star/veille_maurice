"""Client minimal pour l'API Apify (acteurs Facebook Pages/Groupes).

Utilise l'endpoint synchrone "run-sync-get-dataset-items" : lance l'acteur
et attend le résultat en une seule requête HTTP, sans boucle de polling.
"""
from __future__ import annotations

import os

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

APIFY_API_BASE = "https://api.apify.com/v2"


class ErreurApify(RuntimeError):
    pass


class ClientApify:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("APIFY_API_TOKEN")
        if not self.token:
            raise ErreurApify("APIFY_API_TOKEN manquante")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=3, min=3, max=15),
        retry=retry_if_exception_type(ErreurApify),
        reraise=True,
    )
    def executer_acteur(self, acteur_id: str, entree: dict, *, timeout: float = 180.0) -> list[dict]:
        """Lance `acteur_id` avec `entree` et retourne les items du dataset.

        `acteur_id` au format "proprietaire/nom" (ex: "apify/facebook-posts-scraper").
        """
        url = f"{APIFY_API_BASE}/acts/{acteur_id.replace('/', '~')}/run-sync-get-dataset-items"
        try:
            reponse = httpx.post(
                url,
                params={"token": self.token, "timeout": int(timeout)},
                json=entree,
                timeout=timeout + 10,
            )
        except httpx.RequestError as exc:
            raise ErreurApify(f"erreur réseau vers Apify : {exc}") from exc

        if reponse.status_code == 429:
            raise ErreurApify(f"limite de débit Apify atteinte : {reponse.text[:500]}")
        try:
            reponse.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ErreurApify(f"erreur Apify ({reponse.status_code}) : {reponse.text[:500]}") from exc

        return reponse.json()
