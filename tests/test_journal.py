from collecte.journal import Journal


class StockageFactice:
    def __init__(self, *, echoue: bool = False):
        self.echoue = echoue
        self.appels: list[dict] = []

    def journaliser(self, execution_id, *, source_id, niveau, message, details):
        if self.echoue:
            raise ConnectionError("panne réseau simulée")
        self.appels.append(
            {"execution_id": execution_id, "source_id": source_id, "niveau": niveau, "message": message}
        )


class TestJournal:
    def test_ecrit_en_base_en_mode_normal(self):
        stockage = StockageFactice()
        journal = Journal(stockage, "exec-1", mode_test=False)
        journal.info("test")
        assert len(stockage.appels) == 1

    def test_mode_test_n_ecrit_rien_en_base(self):
        stockage = StockageFactice()
        journal = Journal(stockage, "exec-1", mode_test=True)
        journal.erreur("test")
        assert stockage.appels == []

    def test_echec_ecriture_base_ne_leve_pas(self, capsys):
        # Une panne réseau passagère lors de la journalisation elle-même ne
        # doit jamais faire planter le job (voir incident réel : ConnectError
        # pendant journal.erreur() a fait crasher toute la collecte).
        stockage = StockageFactice(echoue=True)
        journal = Journal(stockage, "exec-1", mode_test=False)
        journal.erreur("échec de la collecte : quelque chose", source_id="abc")
        sortie = capsys.readouterr().out
        assert "échec de la collecte : quelque chose" in sortie
        assert "échec d'écriture du journal en base" in sortie
