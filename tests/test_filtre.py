from collecte.filtre import Criteres, FourchetteBudget, filtrer

CRITERES = Criteres(
    budgets_par_type={
        "maison": FourchetteBudget(min_roupies=5_000_000, max_roupies=10_000_000),
        "terrain": FourchetteBudget(min_roupies=3_500_000, max_roupies=10_000_000),
    },
    mots_exclus=("pds", "irs", "res", "à louer", "a louer", "sur plan"),
)


def test_retient_annonce_conforme():
    resultat = filtrer(
        texte_complet="Maison à vendre à Grand Baie",
        prix_roupies=7_000_000,
        secteur_id="grand_baie",
        type_bien="maison",
        criteres=CRITERES,
    )
    assert resultat.retenue is True


def test_retient_terrain_sous_le_budget_maison_mais_dans_le_sien():
    # Le terrain a sa propre fourchette (3,5M-10M), plus basse que la
    # maison (5M-10M) : un terrain à 4M doit passer.
    resultat = filtrer(
        texte_complet="Terrain à vendre à Grand Baie",
        prix_roupies=4_000_000,
        secteur_id="grand_baie",
        type_bien="terrain",
        criteres=CRITERES,
    )
    assert resultat.retenue is True


def test_rejette_maison_au_meme_prix_que_le_terrain_accepte():
    # Le même prix (4M) doit être rejeté pour une maison, dont le plancher
    # est plus haut (5M) que celui du terrain.
    resultat = filtrer(
        texte_complet="Maison à vendre à Grand Baie",
        prix_roupies=4_000_000,
        secteur_id="grand_baie",
        type_bien="maison",
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "prix_sous_budget"


def test_rejette_mot_exclu_location():
    resultat = filtrer(
        texte_complet="Maison à louer à Grand Baie",
        prix_roupies=7_000_000,
        secteur_id="grand_baie",
        type_bien="maison",
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
        type_bien="terrain",
        criteres=CRITERES,
    )
    assert resultat.retenue is True


def test_rejette_pds():
    resultat = filtrer(
        texte_complet="Villa PDS à Grand Baie",
        prix_roupies=7_000_000,
        secteur_id="grand_baie",
        type_bien="maison",
        criteres=CRITERES,
    )
    assert resultat.retenue is False


def test_rejette_secteur_non_detecte():
    resultat = filtrer(
        texte_complet="Maison à vendre",
        prix_roupies=7_000_000,
        secteur_id=None,
        type_bien="maison",
        criteres=CRITERES,
    )
    assert resultat.retenue is False
    assert resultat.raison_rejet == "secteur_non_detecte"


def test_rejette_type_bien_non_detecte():
    resultat = filtrer(
        texte_complet="Belle opportunité à Grand Baie",
        prix_roupies=7_000_000,
        secteur_id="grand_baie",
        type_bien=None,
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "type_bien_non_detecte"


def test_rejette_type_bien_non_accepte():
    resultat = filtrer(
        texte_complet="Appartement à vendre à Grand Baie",
        prix_roupies=7_000_000,
        secteur_id="grand_baie",
        type_bien="autre",
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "type_bien_non_accepte"


def test_rejette_prix_sous_budget():
    resultat = filtrer(
        texte_complet="Terrain à Grand Baie",
        prix_roupies=2_000_000,
        secteur_id="grand_baie",
        type_bien="terrain",
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "prix_sous_budget"


def test_rejette_prix_au_dessus_budget():
    resultat = filtrer(
        texte_complet="Villa à Grand Baie",
        prix_roupies=15_000_000,
        secteur_id="grand_baie",
        type_bien="maison",
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "prix_au_dessus_budget"


def test_rejette_prix_manquant():
    resultat = filtrer(
        texte_complet="Terrain à Grand Baie",
        prix_roupies=None,
        secteur_id="grand_baie",
        type_bien="terrain",
        criteres=CRITERES,
    )
    assert resultat.raison_rejet == "prix_non_detecte"
