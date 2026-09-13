"""Client minimal pour l'API REST Google AI Studio (Gemini Flash).

Utilisé pour (1) l'extraction de repli quand JSON-LD/OpenGraph ne suffisent
pas, et (2) la notation des annonces. Toujours en sortie JSON structurée
(responseMimeType + responseSchema) pour éviter le parsing fragile de texte
libre.

Le nom exact du modèle Flash gratuit peut changer avec le temps : vérifie
dans Google AI Studio (aistudio.google.com) le modèle actif sur le plan
gratuit et ajuste GEMINI_MODEL dans .env si besoin (voir README).
"""
from __future__ import annotations

import json
import os

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
# Vérifié en direct (sept. 2026) : l'alias "gemini-flash-latest" pointait
# vers un modèle preview (gemini-3.8-flash) au quota gratuit anormalement
# bas (20 requêtes/jour). gemini-3.6-flash, le modèle stable recommandé
# par Google au même moment, fonctionne normalement. Ce nom devra
# probablement être revérifié périodiquement — voir README.
MODELE_PAR_DEFAUT = "gemini-3.6-flash"


class ErreurGemini(RuntimeError):
    pass


class ClientGemini:
    def __init__(self, cle_api: str | None = None, modele: str | None = None):
        self.cle_api = cle_api or os.environ.get("GEMINI_API_KEY")
        if not self.cle_api:
            raise ErreurGemini("GEMINI_API_KEY manquante")
        self.modele = modele or os.environ.get("GEMINI_MODEL", MODELE_PAR_DEFAUT)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(ErreurGemini),
        reraise=True,  # sans ça, tenacity enveloppe l'échec final dans RetryError,
        # ce qui empêche l'appelant d'attraper ErreurGemini spécifiquement.
    )
    def generer_json(
        self, prompt: str, *, schema: dict | None = None, timeout: float = 30.0
    ) -> dict:
        url = f"{GEMINI_API_BASE}/models/{self.modele}:generateContent"
        config_generation: dict = {"responseMimeType": "application/json"}
        if schema:
            config_generation["responseSchema"] = schema

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": config_generation,
        }

        try:
            reponse = httpx.post(url, params={"key": self.cle_api}, json=payload, timeout=timeout)
        except httpx.RequestError as exc:
            raise ErreurGemini(f"erreur réseau vers Gemini : {exc}") from exc

        if reponse.status_code == 429:
            # Quota gratuit dépassé pour la minute/le jour.
            raise ErreurGemini(f"limite de débit Gemini atteinte : {reponse.text}")
        if reponse.status_code >= 500:
            # Surcharge temporaire côté Google (fréquent sur le plan gratuit) :
            # convertie en ErreurGemini pour que tenacity la réessaie.
            raise ErreurGemini(f"Gemini indisponible ({reponse.status_code}) : {reponse.text}")
        try:
            reponse.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ErreurGemini(f"erreur Gemini ({reponse.status_code}) : {reponse.text}") from exc

        data = reponse.json()
        try:
            texte = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(texte)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ErreurGemini(f"réponse Gemini inattendue : {data}") from exc
