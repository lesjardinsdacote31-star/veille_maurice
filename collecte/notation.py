"""Notation des annonces par Gemini Flash : score, résumé, drapeaux.

Les votes passés de l'utilisateur (👍/🚫) sont injectés dans le prompt
comme exemples de goût, pour que la notation s'affine avec le temps
(cf. boucle d'apprentissage — voir README, section évolution).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .extraction import DonneesBrutesAnnonce
from .gemini_client import ClientGemini

SCHEMA_NOTATION = {
    "type": "object",
    "properties": {
        "score": {"type": "number"},
        "resume": {"type": "string"},
        "localisation_precise": {"type": "string"},
        "distance_plage_estimee_km": {"type": "number"},
        "vendeur_type": {"type": "string", "enum": ["particulier", "agence", "inconnu"]},
        "drapeaux": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "resume", "drapeaux"],
}


@dataclass
class Notation:
    score: float
    resume: str
    drapeaux: list[str] = field(default_factory=list)
    localisation_precise: str | None = None
    distance_plage_estimee_km: float | None = None
    vendeur_type: str = "inconnu"


def _formater_exemples_votes(votes_passes: list[dict]) -> str:
    if not votes_passes:
        return "(aucun historique de votes pour l'instant)"

    lignes = []
    for vote in votes_passes[-20:]:  # se limite aux votes récents pour garder un prompt compact
        emoji = "👍" if vote["valeur"] == "pour" else "🚫"
        lignes.append(f"- {emoji} {vote.get('titre', '(sans titre)')} — {vote.get('resume', '')}")
    return "\n".join(lignes)


def construire_prompt(donnees: DonneesBrutesAnnonce, votes_passes: list[dict]) -> str:
    return f"""Tu notes une annonce immobilière mauricienne pour un acheteur
qui cherche une maison individuelle ou un terrain constructible, entre 5 et
10 millions de roupies, proche de la plage, dans l'un de ces secteurs du
Nord : Trou aux Biches, Mont Choisy, Pointe aux Canonniers, Grand Baie,
Péreybère, Bain Boeuf, Cap Malheureux. Les travaux sont acceptés si le prix
le justifie. Aucune location, aucun programme PDS/IRS/RES, aucune vente sur
plan ne l'intéresse.

Voici ses votes passés sur d'autres annonces, à titre d'exemples de goût :
{_formater_exemples_votes(votes_passes)}

Annonce à noter :
Titre : {donnees.titre}
Prix : {donnees.prix_roupies} Rs
Texte complet (peut inclure du texte OCR extrait de photos) :
{donnees.texte_complet[:6000]}

Réponds uniquement avec le JSON demandé :
- score : note sur 10 (10 = correspond exactement à ce qu'il cherche)
- resume : deux phrases maximum
- localisation_precise : la localisation la plus précise que tu peux déduire du texte
- distance_plage_estimee_km : estimation à partir du texte, null si impossible à évaluer
- vendeur_type : "particulier", "agence" ou "inconnu"
- drapeaux : liste de points de vigilance (ex: "prix nettement sous le marché",
  "informations contradictoires", "photo de document administratif plutôt que du bien")
"""


def noter_annonce(
    client: ClientGemini, donnees: DonneesBrutesAnnonce, votes_passes: list[dict]
) -> Notation:
    prompt = construire_prompt(donnees, votes_passes)
    resultat = client.generer_json(prompt, schema=SCHEMA_NOTATION)

    return Notation(
        score=float(resultat["score"]),
        resume=resultat["resume"],
        drapeaux=resultat.get("drapeaux", []),
        localisation_precise=resultat.get("localisation_precise"),
        distance_plage_estimee_km=resultat.get("distance_plage_estimee_km"),
        vendeur_type=resultat.get("vendeur_type", "inconnu"),
    )
