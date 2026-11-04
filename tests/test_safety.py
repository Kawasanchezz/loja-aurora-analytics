import pytest

from aurora import cli
from aurora.config import Settings
from aurora.safety import confirm_destructive, is_safe_test_database


VALOR_FALSO = "valor-falso-apenas-para-teste"  # não é uma credencial real


def _settings(database="aurora", senha=VALOR_FALSO):
    return Settings(host="127.0.0.1", port=3306, database=database, user="aurora", password=senha, seed=42)


def test_repr_da_configuracao_nao_vaza_a_senha():
    assert VALOR_FALSO not in repr(_settings())
    assert VALOR_FALSO not in str(_settings())


def test_url_continua_levando_a_senha_para_a_conexao():
    assert _settings().url().password == VALOR_FALSO


def test_confirmacao_exige_o_nome_exato_do_banco():
    assert confirm_destructive(_settings(), input_fn=lambda _: "aurora", interactive=True)
    assert confirm_destructive(_settings(), input_fn=lambda _: "  aurora  ", interactive=True)
    assert not confirm_destructive(_settings(), input_fn=lambda _: "banco_aula", interactive=True)
    assert not confirm_destructive(_settings(), input_fn=lambda _: "", interactive=True)
    assert not confirm_destructive(_settings(), input_fn=lambda _: "s", interactive=True)


def test_prompt_mostra_banco_e_servidor():
    mostrado = []
    confirm_destructive(_settings(), input_fn=lambda texto: mostrado.append(texto) or "", interactive=True)
    assert "'aurora'" in mostrado[0] and "127.0.0.1:3306" in mostrado[0]


def test_sem_terminal_e_sem_yes_recusa_sem_perguntar():
    def nao_deve_perguntar(_):
        raise AssertionError("não deveria perguntar sem terminal")
    assert not confirm_destructive(_settings(), input_fn=nao_deve_perguntar, interactive=False)


def test_entrada_fechada_ou_ctrl_c_cancela_sem_erro():
    def fechada(_):
        raise EOFError

    def interrompida(_):
        raise KeyboardInterrupt
    assert not confirm_destructive(_settings(), input_fn=fechada, interactive=True)
    assert not confirm_destructive(_settings(), input_fn=interrompida, interactive=True)


def test_yes_dispensa_a_pergunta():
    assert confirm_destructive(_settings(), assume_yes=True, interactive=False)


@pytest.mark.parametrize("nome, principal, esperado", [
    ("aurora_test", "aurora", True),
    ("aurora", "aurora", False),
    ("banco_aula", "aurora", False),
    ("aurora_testing", "aurora", False),
    ("aurora_test", "aurora_test", False),
])
def test_banco_de_teste_seguro(nome, principal, esperado):
    assert is_safe_test_database(nome, principal) is esperado


@pytest.fixture
def cli_espiao(monkeypatch):
    chamadas = []
    monkeypatch.setattr(cli, "load_settings", lambda: _settings())
    for nome in ("init-db", "seed", "report", "all"):
        monkeypatch.setitem(cli.COMMANDS, nome, lambda *_, n=nome: chamadas.append(n))
    return chamadas


def test_cli_comando_destrutivo_sem_yes_e_sem_terminal_nao_executa(cli_espiao, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert cli.main(["init-db"]) == 1
    assert cli.main(["seed"]) == 1
    assert cli.main(["all"]) == 1
    assert cli_espiao == []


def test_cli_com_yes_executa(cli_espiao):
    assert cli.main(["all", "--yes"]) == 0
    assert cli_espiao == ["all"]


def test_cli_report_nao_pede_confirmacao(cli_espiao, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert cli.main(["report"]) == 0
    assert cli_espiao == ["report"]


def test_cli_confirmacao_interativa_com_nome_certo(cli_espiao, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _: "aurora")
    assert cli.main(["init-db"]) == 0
    assert cli_espiao == ["init-db"]


def test_cli_confirmacao_interativa_com_nome_errado_cancela(cli_espiao, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _: "outro_banco")
    assert cli.main(["seed"]) == 1
    assert cli_espiao == []
