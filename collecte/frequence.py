"""Détermine si une source doit être collectée à ce passage, selon sa
fréquence configurée (les groupes Facebook n'ont pas tous besoin d'être
vérifiés à chaque run — voir README, section budget Facebook).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Marges sous le "vrai" intervalle pour tolérer un run un peu en retard
# (panne, exécution manuelle décalée...) sans sauter un passage.
SEUIL_QUOTIDIEN = timedelta(hours=20)
SEUIL_HEBDOMADAIRE = timedelta(days=6, hours=12)


def est_due(frequence: str, derniere_collecte_le: str | None, *, maintenant: datetime | None = None) -> bool:
    if frequence == "manuel":
        return False
    if frequence == "chaque_run":
        return True
    if not derniere_collecte_le:
        return True

    maintenant = maintenant or datetime.now(timezone.utc)
    derniere = datetime.fromisoformat(derniere_collecte_le.replace("Z", "+00:00"))
    ecart = maintenant - derniere

    if frequence == "quotidien":
        return ecart >= SEUIL_QUOTIDIEN
    if frequence == "hebdomadaire":
        return ecart >= SEUIL_HEBDOMADAIRE

    return True
