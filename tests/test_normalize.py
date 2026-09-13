from collecte.normalize import (
    Secteur,
    detecter_secteur,
    detecter_type_bien,
    normaliser_chambres,
    normaliser_perches,
    normaliser_prix,
    normaliser_telephone,
)


class TestNormaliserPrix:
    def test_multiplicateur_million_point(self):
        assert normaliser_prix("2.7m (negotiable)") == 2_700_000

    def test_multiplicateur_million_mot(self):
        assert normaliser_prix("Prix - Rs 2.6 Million per Lot") == 2_600_000

    def test_multiplicateur_million_virgule(self):
        assert normaliser_prix("RS 24,5 MILLIONS — PRIX NÉGOCIABLE") == 24_500_000

    def test_nombre_brut_avec_virgules(self):
        assert normaliser_prix("VILLA D'EXCEPTION — RS 24,500,000") == 24_500_000

    def test_prix_simple_sans_separateur(self):
        assert normaliser_prix("Prix Rs25000 à debattre") == 25_000

    def test_ignore_petits_nombres_type_telephone_si_grand_nombre_present(self):
        # Le numéro de téléphone (8 chiffres) ne doit pas être pris pour le prix
        # quand un vrai prix est présent.
        assert normaliser_prix("4,000,000 contact 59497477") == 4_000_000

    def test_aucun_prix(self):
        assert normaliser_prix("Belle maison à visiter") is None

    def test_texte_vide(self):
        assert normaliser_prix("") is None


class TestNormaliserPerches:
    def test_perches_simple(self):
        assert normaliser_perches("29.7 perches") == 29.7

    def test_perches_virgule_francaise(self):
        assert normaliser_perches("10,9 perches") == 10.9

    def test_prefere_perches_a_m2_si_les_deux_presents(self):
        assert normaliser_perches("Terrain : 462 m² | 10,9 perches") == 10.9

    def test_conversion_m2_vers_perches(self):
        # 1252 m2 / 42.15 ~= 29.70
        assert normaliser_perches("PIN 1252m²") == round(1252 / 42.15, 2)

    def test_toises_traitees_comme_perches(self):
        assert normaliser_perches("97.2 toises") == 97.2

    def test_aucune_surface(self):
        assert normaliser_perches("Belle maison à visiter") is None


class TestNormaliserTelephone:
    def test_numero_local_simple(self):
        assert normaliser_telephone("Contact Mr Ushal 59497477") == ["23059497477"]

    def test_numero_avec_espaces(self):
        assert normaliser_telephone("WhatsApp: 5949 7477") == ["23059497477"]

    def test_numero_avec_indicatif_espace(self):
        assert normaliser_telephone("+230 5492 4746") == ["23054924746"]

    def test_numero_avec_indicatif_colle(self):
        assert normaliser_telephone("2305492474") == []  # 10 chiffres au total -> invalide

    def test_plusieurs_numeros(self):
        resultat = normaliser_telephone("WhatsApp: 57067541, 52521797")
        assert resultat == ["23057067541", "23052521797"]

    def test_deduplique_numeros_identiques(self):
        resultat = normaliser_telephone("Tel 59155845 ou WhatsApp 59155845")
        assert resultat == ["23059155845"]

    def test_rejette_numero_fixe_invalide(self):
        # Ne commence ni par 5, 8, 9 ni 6 -> pas un mobile/fixe mauricien plausible
        assert normaliser_telephone("Prix 12345678") == []

    def test_aucun_numero(self):
        assert normaliser_telephone("Belle maison à visiter") == []


class TestNormaliserChambres:
    def test_format_bedrooms_titre_reel(self):
        # Format observé sur lexpressproperty.com
        assert normaliser_chambres("House / Villa - 3 Bedrooms - 270 m²") == 3

    def test_format_chambres_francais(self):
        assert normaliser_chambres("Villa avec 4 chambres à coucher") == 4

    def test_aucune_mention(self):
        assert normaliser_chambres("Terrain constructible") is None


class TestDetecterTypeBien:
    def test_terrain_anglais(self):
        assert detecter_type_bien("Residential Land for Sale at Pereybere") == "terrain"

    def test_terrain_francais(self):
        assert detecter_type_bien("Terrain résidentiel à vendre") == "terrain"

    def test_maison_villa(self):
        assert detecter_type_bien("Villa à vendre à Grand Baie") == "maison"

    def test_maison_anglais(self):
        assert detecter_type_bien("House for sale at Terre Rouge") == "maison"

    def test_appartement_classe_comme_autre(self):
        assert detecter_type_bien("Appartement à vendre à Balaclava") == "autre"

    def test_penthouse_classe_comme_autre(self):
        assert detecter_type_bien("Penthouse à Vendre à Grand Baie") == "autre"

    def test_aucun_mot_cle(self):
        assert detecter_type_bien("Belle opportunité à ne pas manquer") is None

    def test_terrain_prioritaire_sur_mention_de_contact_office(self):
        # Régression : "Office: 5433 0678" (numéro de l'agence) ne doit pas
        # faire classer un terrain comme "autre" (bug observé en conditions
        # réelles — le mot générique "office" arrivait en fin de texte).
        texte = (
            "RESIDENTIAL LAND FOR SALE AT PEREYBERE. An excellent opportunity. "
            "For more information: Office: 5433 0678"
        )
        assert detecter_type_bien(texte) == "terrain"

    def test_texte_vide(self):
        assert detecter_type_bien("") is None


class TestDetecterSecteur:
    SECTEURS = [
        Secteur("grand_baie", "Grand Baie", ("grand baie", "grand-baie", "grand bay")),
        Secteur("pereybere", "Péreybère", ("pereybere", "péreybère")),
        Secteur(
            "pointe_aux_canonniers",
            "Pointe aux Canonniers",
            ("pointe aux canonniers", "canonniers"),
        ),
    ]

    def test_detecte_secteur_simple(self):
        assert detecter_secteur("Villa à Grand Baie", self.SECTEURS) == "grand_baie"

    def test_insensible_a_la_casse(self):
        assert detecter_secteur("VILLA A GRAND BAIE", self.SECTEURS) == "grand_baie"

    def test_prefere_alias_le_plus_specifique(self):
        texte = "Terrain à Pointe aux Canonniers, proche Grand Baie"
        assert detecter_secteur(texte, self.SECTEURS) == "pointe_aux_canonniers"

    def test_aucun_secteur_trouve(self):
        assert detecter_secteur("Maison à Flic-en-Flac", self.SECTEURS) is None

    def test_texte_vide(self):
        assert detecter_secteur("", self.SECTEURS) is None
