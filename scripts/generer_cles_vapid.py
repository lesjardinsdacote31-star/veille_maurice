"""Génère une paire de clés VAPID pour les notifications Web Push.

À lancer une seule fois (les clés ne changent pas ensuite — en régénérer
invaliderait tous les abonnements déjà enregistrés côté navigateur).

Usage :
    python -m scripts.generer_cles_vapid
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def generer() -> None:
    cle_privee = ec.generate_private_key(ec.SECP256R1())

    pem_prive = cle_privee.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    nombres_publics = cle_privee.public_key().public_numbers()
    point_brut = b"\x04" + nombres_publics.x.to_bytes(32, "big") + nombres_publics.y.to_bytes(32, "big")
    cle_publique_b64url = base64.urlsafe_b64encode(point_brut).rstrip(b"=").decode()

    print("=" * 70)
    print("VAPID_PRIVATE_KEY (secret GitHub Actions — collecte.yml) :")
    print("=" * 70)
    print(pem_prive)
    print("=" * 70)
    print("VITE_VAPID_PUBLIC_KEY (variable de build Cloudflare, publique) :")
    print("=" * 70)
    print(cle_publique_b64url)
    print()
    print("Colle le bloc PEM complet (avec les lignes BEGIN/END) tel quel")
    print("dans le secret GitHub VAPID_PRIVATE_KEY, et la ligne unique")
    print("ci-dessus dans la variable de build Cloudflare VITE_VAPID_PUBLIC_KEY")
    print("et dans app/.env en local.")


if __name__ == "__main__":
    generer()
