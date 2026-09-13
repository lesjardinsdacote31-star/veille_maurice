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
from tenacity import retry, stop_after_attempt, wait_exponential

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODELE_PAR_DEFAUT = "gemini-flash-latest"


class ErreurGemini(RuntimeError):
    pass


class ClientGemini:
    def __init__(self, cle_api: str | None = None, modele: str | None = None):
        self.cle_api = cle_api or os.environ.get("GEMINI_API_KEY")
        if not self.cle_api:
            raise ErreurGemini("GEMINI_API_KEY manquante")
        self.modele = modele or os.environ.get("GEMINI_MODEL", MODELE_PAR_DEFAUT)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
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

        reponse = httpx.post(url, params={"key": self.cle_api}, json=payload, timeout=timeout)

        if reponse.status_code == 429:
            # Quota gratuit dépassé pour la minute/le jour : on laisse tenacity
            # réessayer avec backoff, l'appelant doit rester tolérant à l'échec finale.
            raise ErreurGemini(f"limite de débit Gemini atteinte : {reponse.text}")
        reponse.raise_for_status()

        data = reponse.json()
        try:
            texte = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(texte)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ErreurGemini(f"réponse Gemini inattendue : {data}") from exc
