from collecte.dedup import (
    AnnoncePourDedup,
    construire_cle_dedup,
    prix_dans_tolerance,
    sont_probablement_doublons,
    surface_dans_tolerance,
)


class TestConstruireCleDedup:
    def test_avec_telephone(self):
        assert construire_cle_dedup(["23059497477"]) == "tel:23059497477"

    def test_prend_le_premier_telephone(self):
        assert construire_cle_dedup(["23059497477", "23052521797"]) == "tel:23059497477"

    def test_sans_telephone(self):
        assert construire_cle_dedup([]) is None


class TestPrixDansTolerance:
    def test_prix_identiques(self):
        assert prix_dans_tolerance(2_700_000, 2_700_000) is True

    def test_ecart_sous_le_seuil(self):
        # 2% d'écart, tolérance par défaut 3%
        assert prix_dans_tolerance(2_700_000, 2_754_000) is True

    def test_ecart_au_dessus_du_seuil(self):
        # 5% d'écart
        assert prix_dans_tolerance(2_700_000, 2_835_000) is False

    def test_valeur_manquante(self):
        assert prix_dans_tolerance(None, 2_700_000) is False
        assert prix_dans_tolerance(2_700_000, None) is False

    def test_tolerance_personnalisee(self):
        assert prix_dans_tolerance(1_000_000, 1_100_000, tolerance=0.10) is True
        assert prix_dans_tolerance(1_000_000, 1_150_000, tolerance=0.10) is False


class TestSurfaceDansTolerance:
    def test_dans_la_marge(self):
        assert surface_dans_tolerance(29.7, 30.0) is True

    def test_hors_marge(self):
        assert surface_dans_tolerance(29.7, 35.0) is False

    def test_valeur_manquante(self):
        assert surface_dans_tolerance(None, 29.7) is False


class TestSontProbablementDoublons:
    def test_meme_telephone_meme_prix(self):
        a = AnnoncePourDedup(telephones=("23059497477",), prix_roupies=2_700_000)
        b = AnnoncePourDedup(telephones=("23059497477",), prix_roupies=2_700_000)
        assert sont_probablement_doublons(a, b) is True

    def test_meme_telephone_prix_proche(self):
        # Cas réel observé : republication du même mandat avec un prix
        # légèrement retouché (négociation affichée différemment).
        a = AnnoncePourDedup(telephones=("23059497477",), prix_roupies=2_700_000)
        b = AnnoncePourDedup(telephones=("23059497477",), prix_roupies=2_730_000)
        assert sont_probablement_doublons(a, b) is True

    def test_meme_telephone_prix_trop_different(self):
        a = AnnoncePourDedup(telephones=("23059497477",), prix_roupies=2_700_000)
        b = AnnoncePourDedup(telephones=("23059497477",), prix_roupies=4_000_000)
        assert sont_probablement_doublons(a, b) is False

    def test_telephones_differents(self):
        a = AnnoncePourDedup(telephones=("23059497477",), prix_roupies=2_700_000)
        b = AnnoncePourDedup(telephones=("23052521797",), prix_roupies=2_700_000)
        assert sont_probablement_doublons(a, b) is False

    def test_aucun_telephone(self):
        a = AnnoncePourDedup(telephones=(), prix_roupies=2_700_000)
        b = AnnoncePourDedup(telephones=(), prix_roupies=2_700_000)
        assert sont_probablement_doublons(a, b) is False

    def test_un_telephone_commun_parmi_plusieurs(self):
        a = AnnoncePourDedup(telephones=("23059497477", "23050000000"), prix_roupies=2_700_000)
        b = AnnoncePourDedup(telephones=("23011111111", "23059497477"), prix_roupies=2_700_000)
        assert sont_probablement_doublons(a, b) is True
