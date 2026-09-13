from datetime import datetime, timedelta, timezone

from collecte.frequence import est_due

MAINTENANT = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def test_manuel_jamais_du():
    assert est_due("manuel", None, maintenant=MAINTENANT) is False
    assert est_due("manuel", MAINTENANT.isoformat(), maintenant=MAINTENANT) is False


def test_chaque_run_toujours_du():
    assert est_due("chaque_run", MAINTENANT.isoformat(), maintenant=MAINTENANT) is True


def test_jamais_collecte_est_du():
    assert est_due("quotidien", None, maintenant=MAINTENANT) is True
    assert est_due("hebdomadaire", None, maintenant=MAINTENANT) is True


def test_quotidien_pas_encore_du():
    derniere = (MAINTENANT - timedelta(hours=5)).isoformat()
    assert est_due("quotidien", derniere, maintenant=MAINTENANT) is False


def test_quotidien_du():
    derniere = (MAINTENANT - timedelta(hours=21)).isoformat()
    assert est_due("quotidien", derniere, maintenant=MAINTENANT) is True


def test_hebdomadaire_pas_encore_du():
    derniere = (MAINTENANT - timedelta(days=3)).isoformat()
    assert est_due("hebdomadaire", derniere, maintenant=MAINTENANT) is False


def test_hebdomadaire_du():
    derniere = (MAINTENANT - timedelta(days=7)).isoformat()
    assert est_due("hebdomadaire", derniere, maintenant=MAINTENANT) is True


def test_gere_le_suffixe_z():
    derniere = (MAINTENANT - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    assert est_due("quotidien", derniere, maintenant=MAINTENANT) is False
