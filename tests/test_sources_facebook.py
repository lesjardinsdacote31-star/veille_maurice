from collecte.sources_facebook import convertir_post

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
