from collecte.extraction import extraire_annonce

HTML_AVEC_NAV_POLLUANTE = """
<html>
<head>
<meta property="og:title" content="Terrain à Vendre à Péreybère | Rs 6,500,000" />
<meta property="og:description" content="Beau terrain de 15 perches proche de la plage." />
</head>
<body>
<nav>Parcourir par secteur : Trou aux Biches, Grand Baie, Mont Choisy, Péreybère, Cap Malheureux</nav>
<main>Terrain à Vendre à Péreybère - Rs 6,500,000 - 15 perches</main>
<aside>Biens similaires : Villa à Trou aux Biches, Appartement à Grand Baie</aside>
</body>
</html>
"""


def test_description_courte_exclut_la_navigation_du_site():
    """Régression : la détection de secteur ne doit pas être polluée par un
    menu de navigation listant tous les secteurs sur chaque page du site
    (bug observé en conditions réelles sur un vrai site immobilier).
    """
    donnees = extraire_annonce(HTML_AVEC_NAV_POLLUANTE, "https://example.mu/annonce/1")

    assert "Péreybère" in donnees.description_courte
    assert "Trou aux Biches" not in donnees.description_courte
    assert "Grand Baie" not in donnees.description_courte

    # Le texte complet (utilisé par Gemini, moins sensible aux faux positifs
    # de sous-chaîne) peut lui contenir la nav — ce n'est pas le problème ici.
    assert "Trou aux Biches" in donnees.texte_complet
