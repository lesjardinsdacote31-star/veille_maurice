from collecte.sources_facebook import collecter_facebook_groupe, convertir_post

# Structure calquée sur un vrai post récupéré via l'acteur Apify
# apify/facebook-groups-scraper (voir historique du projet).
POST_TERRAIN_AVEC_OCR = {
    "facebookUrl": "https://www.facebook.com/groups/901873673838148/",
    "text": (
        "Agriculture land for sale at Triolet pointe aux piments\n29.7 perches \n\n"
        "Plot D10\n\nPossibility of land conversion\n\n2 road access \n\n"
        "CEB and CWA facilities available on site\n\n2.7m (negotiable)\n\n"
        "Contact Mr Ushal 59497477"
    ),
    "attachments": [
        {"mediaset_token": "pcb.123"},
        {"thumbnail": "https://exemple.mu/photo1.jpg", "ocrText": "PIN 1252m²"},
    ],
    "user": {"id": "61586820990383", "name": "MT property"},
    "likesCount": 0,
    "commentsCount": 0,
}

POST_SANS_TEXTE_NI_OCR = {
    "facebookUrl": "https://www.facebook.com/groups/901873673838148/",
    "text": "",
    "user": {"id": "100062684624630", "name": "Burth Immoblier"},
}

POST_TEXTE_UNIQUEMENT_DANS_OCR = {
    "facebookUrl": "https://www.facebook.com/groups/901873673838148/",
    "text": "",
    "attachments": [
        {
            "thumbnail": "https://exemple.mu/photo.jpg",
            "ocrText": "Residential Land for sale Goodlands Rs 2.9M 369.3m²",
        }
    ],
}


class TestConvertirPost:
    def test_extrait_prix_secteur_telephone_depuis_texte_et_ocr(self):
        donnees = convertir_post(POST_TERRAIN_AVEC_OCR)
        assert donnees is not None
        assert donnees.prix_roupies == 2_700_000
        assert donnees.telephones == ["23059497477"]
        assert donnees.type_bien == "terrain"
        assert donnees.url == "https://www.facebook.com/groups/901873673838148/"

    def test_inclut_le_texte_ocr_dans_le_texte_complet(self):
        donnees = convertir_post(POST_TERRAIN_AVEC_OCR)
        assert "1252m²" in donnees.texte_complet

    def test_post_sans_texte_ni_ocr_ignore(self):
        assert convertir_post(POST_SANS_TEXTE_NI_OCR) is None

    def test_texte_uniquement_dans_ocr_est_exploite(self):
        donnees = convertir_post(POST_TEXTE_UNIQUEMENT_DANS_OCR)
        assert donnees is not None
        assert donnees.prix_roupies == 2_900_000
        assert donnees.type_bien == "terrain"

    def test_titre_derive_du_debut_du_texte(self):
        donnees = convertir_post(POST_TERRAIN_AVEC_OCR)
        assert donnees.titre.startswith("Agriculture land for sale at Triolet")

    def test_description_courte_egale_texte_complet(self):
        # Contrairement aux sites web, un post FB isolé n'a pas de pollution
        # de page (menus, biens similaires) à filtrer.
        donnees = convertir_post(POST_TERRAIN_AVEC_OCR)
        assert donnees.description_courte == donnees.texte_complet


class ClientApifyFactice:
    """Double de test : capture l'entrée reçue, renvoie une liste de posts
    fournie d'avance, sans appel réseau réel."""

    def __init__(self, posts_a_renvoyer: list[dict]):
        self.posts_a_renvoyer = posts_a_renvoyer
        self.dernier_acteur_id: str | None = None
        self.derniere_entree: dict | None = None

    def executer_acteur(self, acteur_id: str, entree: dict, *, timeout: float = 180.0) -> list[dict]:
        self.dernier_acteur_id = acteur_id
        self.derniere_entree = entree
        return self.posts_a_renvoyer


class TestCollecterFacebookGroupe:
    def test_regroupe_un_seul_lancement_pour_plusieurs_sources(self):
        # Un post par groupe, comme observé en conditions réelles avec
        # resultsLimit appliqué par URL et non globalement.
        posts = [
            {**POST_TERRAIN_AVEC_OCR, "facebookUrl": "https://www.facebook.com/groups/AAA/"},
            {**POST_TERRAIN_AVEC_OCR, "facebookUrl": "https://www.facebook.com/groups/BBB/"},
        ]
        client = ClientApifyFactice(posts)
        sources = [
            {"type": "groupe_facebook", "identifiant": "https://www.facebook.com/groups/AAA/"},
            {"type": "groupe_facebook", "identifiant": "https://www.facebook.com/groups/BBB/"},
        ]

        resultat = collecter_facebook_groupe(sources, client_apify=client)

        assert client.dernier_acteur_id == "apify/facebook-groups-scraper"
        assert len(client.derniere_entree["startUrls"]) == 2
        assert len(resultat["https://www.facebook.com/groups/AAA/"]) == 1
        assert len(resultat["https://www.facebook.com/groups/BBB/"]) == 1

    def test_utilise_la_plus_ancienne_date_du_lot(self):
        client = ClientApifyFactice([])
        sources = [
            {
                "type": "page_facebook",
                "identifiant": "https://www.facebook.com/a",
                "derniere_collecte_le": "2026-09-10T08:00:00+00:00",
            },
            {
                "type": "page_facebook",
                "identifiant": "https://www.facebook.com/b",
                "derniere_collecte_le": "2026-09-05T08:00:00+00:00",
            },
        ]

        collecter_facebook_groupe(sources, client_apify=client)

        assert client.derniere_entree["onlyPostsNewerThan"] == "2026-09-05"

    def test_pas_de_filtre_date_si_une_source_jamais_collectee(self):
        client = ClientApifyFactice([])
        sources = [
            {"type": "page_facebook", "identifiant": "https://www.facebook.com/a",
             "derniere_collecte_le": "2026-09-10T08:00:00+00:00"},
            {"type": "page_facebook", "identifiant": "https://www.facebook.com/b"},
        ]

        collecter_facebook_groupe(sources, client_apify=client)

        assert "onlyPostsNewerThan" not in client.derniere_entree

    def test_liste_vide_ne_lance_rien(self):
        client = ClientApifyFactice([])
        assert collecter_facebook_groupe([], client_apify=client) == {}
        assert client.dernier_acteur_id is None
