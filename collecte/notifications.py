"""Envoi de notifications Web Push (VAPID) depuis le job de collecte.

Couche d'abstraction côté serveur : c'est le seul module qui connaît
pywebpush/VAPID. Basculer vers Firebase Cloud Messaging plus tard (si
passage à Capacitor) reviendrait à ne changer que ce fichier — voir
app/CAPACITOR.md pour le pendant côté navigateur.
"""
from __future__ import annotations

import json
import os

from pywebpush import WebPushException, webpush

from .stockage import Stockage


class ErreurNotification(RuntimeError):
    pass


def _cle_privee_et_claims() -> tuple[str, dict]:
    cle_privee = os.environ.get("VAPID_PRIVATE_KEY")
    email_contact = os.environ.get("VAPID_CONTACT_EMAIL")
    if not cle_privee or not email_contact:
        raise ErreurNotification("VAPID_PRIVATE_KEY ou VAPID_CONTACT_EMAIL manquante")
    return cle_privee, {"sub": f"mailto:{email_contact}"}


def envoyer_a_tous(
    stockage: Stockage, *, titre: str, corps: str, url: str, mode_test: bool
) -> int:
    """Envoie une notification à tous les abonnements actifs. Retourne le
    nombre d'envois réussis. Un abonnement expiré (404/410) est désactivé
    automatiquement plutôt que de faire échouer l'envoi aux autres.
    """
    if mode_test:
        return 0

    cle_privee, claims = _cle_privee_et_claims()
    abonnements = stockage.charger_abonnements_actifs()

    charge_utile = json.dumps({"titre": titre, "corps": corps, "url": url})

    nb_reussis = 0
    for abonnement in abonnements:
        subscription_info = {
            "endpoint": abonnement["endpoint"],
            "keys": abonnement["clefs"],
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=charge_utile,
                vapid_private_key=cle_privee,
                vapid_claims=dict(claims),
            )
            nb_reussis += 1
        except WebPushException as exc:
            code_reponse = exc.response.status_code if exc.response is not None else None
            if code_reponse in (404, 410):
                stockage.desactiver_abonnement(abonnement["id"])
            # Un échec sur un abonnement ne doit jamais interrompre les autres.

    return nb_reussis


def construire_message(annonce: dict) -> tuple[str, str, str]:
    """Construit (titre, corps, url) pour la notification d'une nouvelle
    annonce. Fonction pure, testable sans dépendance réseau.
    """
    titre = annonce.get("titre") or "Nouvelle annonce"
    prix = annonce.get("prix_roupies")
    corps_prix = f"{prix:,.0f} Rs".replace(",", " ") if prix else "prix non détecté"
    score = annonce.get("score")
    corps = corps_prix + (f" · noté {score}/10" if score is not None else "")
    url = f"/#/annonce/{annonce['id']}" if annonce.get("id") else "/"
    return titre, corps, url


def notifier_nouvelle_annonce(stockage: Stockage, annonce: dict, *, mode_test: bool) -> None:
    titre, corps, url = construire_message(annonce)
    envoyer_a_tous(stockage, titre=titre, corps=corps, url=url, mode_test=mode_test)
