from collecte.filtre import Criteres, filtrer

CRITERES = Criteres(
    budget_min_roupies=5_000_000,
    budget_max_roupies=10_000_000,
    types_acceptes=("maison", "terrain"),
    mots_exclus=("pds", "irs", "res", "à louer", "a louer", "sur plan"),
)


def test_retient_annonce_conforme():
    resultat = filtrer(
        texte_complet="Maison à vendre à Grand Baie",
        prix_roupies=7_000_000,
        secteur_id="grand_baie",
        criteres=CRITERES,
    )
    assert resultat.retenue is True


def test_rejette_mot_exclu_location():
    resultat = filtrer(
        texte_complet="Maison à louer à Grand Baie",
        prix_roupies=7_000_000,
        secteur_id="grand_baie",
        criteres=CRITERES,
    )
    assert resultat.retenue is False
    assert resultat.raison_rejet.startswith("mot_exclu")


def test_naccepte_pas_residentiel_comme_faux_positif_de_res():
    # Régression : "res" (RES = Real Estate Scheme) ne doit pas matcher en
    # sous-chaîne le mot "résidentiel"/"residential", omniprésent dans les
    # annonces immobilières légitimes (bug observé en conditions réelles).
    resultat = filtrer(
        texte_complet="RESIDENTIAL LAND FOR SALE AT PEREYBERE",
        prix_roupies=8_500_000,
        secteur_id="pereybere",
        criteres=CRITERES,
    )
    assert resultat.retenue is True


def test_rejette_pds():
    resultat = filtrer(
        texte_complet="Villa PDS à Grand Baie",
        prix_roupies=7_000_000,
        secteur_id="grand_baie",
        criteres=CRITERES,
    )
    assert resultat.retenue is False


def test_rejette_secteur_non_detecte():
    resultat = filtrer(
        texte_complet="Maison à vendre",
        prix_roupies=7_000_000,
        secteur_id=None,
        criteres=CRITERES,
    )
    assert resultat.retenue is False
    assert resultat.raison_rejet == "secteur_non_detecte"


def test_rejette_prix_sous_budget():
    resultat = filtrer(
        texte_complet="Terrain à Grand Baie",
        prix_roupies=2_000_000,
        secteur_id="grand_baie",
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "prix_sous_budget"


def test_rejette_prix_au_dessus_budget():
    resultat = filtrer(
        texte_complet="Villa à Grand Baie",
        prix_roupies=15_000_000,
        secteur_id="grand_baie",
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "prix_au_dessus_budget"


def test_rejette_prix_manquant():
    resultat = filtrer(
        texte_complet="Terrain à Grand Baie",
        prix_roupies=None,
        secteur_id="grand_baie",
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "prix_non_detecte"
