"""Journalisation d'une exécution : toujours affichée sur stdout (visible
dans les logs GitHub Actions), et persistée en base sauf en mode test.
"""
from __future__ import annotations

from .stockage import Stockage


class Journal:
    def __init__(self, stockage: Stockage | None, execution_id: str, mode_test: bool):
        self.stockage = stockage
        self.execution_id = execution_id
        self.mode_test = mode_test

    def _log(self, niveau: str, message: str, source_id: str | None, details: dict) -> None:
        prefixe = f"[{niveau.upper()}]"
        suffixe = f" source={source_id}" if source_id else ""
        print(f"{prefixe} {message}{suffixe} {details if details else ''}".rstrip())

        if not self.mode_test and self.stockage is not None:
            try:
                self.stockage.journaliser(
                    self.execution_id,
                    source_id=source_id,
                    niveau=niveau,
                    message=message,
                    details=details,
                )
            except Exception as exc:  # noqa: BLE001 — la journalisation ne doit
                # jamais faire planter le job (ex: coupure réseau passagère
                # vers Supabase) ; le message reste visible via le print()
                # ci-dessus (stdout, capturé par les logs GitHub Actions).
                print(f"[AVERTISSEMENT] échec d'écriture du journal en base : {exc}")

    def info(self, message: str, *, source_id: str | None = None, **details) -> None:
        self._log("info", message, source_id, details)

    def avertissement(self, message: str, *, source_id: str | None = None, **details) -> None:
        self._log("avertissement", message, source_id, details)

    def erreur(self, message: str, *, source_id: str | None = None, **details) -> None:
        self._log("erreur", message, source_id, details)
