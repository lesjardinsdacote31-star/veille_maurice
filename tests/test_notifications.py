from collecte.notifications import construire_message


def test_message_avec_prix_et_score():
    titre, corps, url = construire_message(
        {"id": "abc-123", "titre": "Terrain à Péreybère", "prix_roupies": 5_900_000, "score": 9.5}
    )
    assert titre == "Terrain à Péreybère"
    assert corps == "5 900 000 Rs · noté 9.5/10"
    assert url == "/#/annonce/abc-123"


def test_message_sans_prix():
    _, corps, _ = construire_message({"id": "abc", "titre": "Annonce", "prix_roupies": None, "score": 7})
    assert "prix non détecté" in corps


def test_message_sans_score():
    _, corps, _ = construire_message(
        {"id": "abc", "titre": "Annonce", "prix_roupies": 4_000_000, "score": None}
    )
    assert "noté" not in corps


def test_titre_par_defaut_si_absent():
    titre, _, _ = construire_message({"id": "abc", "prix_roupies": None, "score": None})
    assert titre == "Nouvelle annonce"


def test_url_racine_si_pas_d_id():
    _, _, url = construire_message({"titre": "x", "prix_roupies": None, "score": None})
    assert url == "/"
