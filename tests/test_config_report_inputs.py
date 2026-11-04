from types import SimpleNamespace

import pandas as pd
import pytest

from aurora import config
from aurora.report import check_inputs

VALOR_FALSO = "valor-falso-apenas-para-teste"  # não é uma credencial real
VARIAVEIS = {"MYSQL_DATABASE": "aurora", "MYSQL_USER": "u", "MYSQL_PASSWORD": VALOR_FALSO}


@pytest.fixture
def ambiente(monkeypatch):
    """Ambiente controlado: ignora um .env real da máquina e limpa as variáveis do projeto."""
    monkeypatch.setattr(config, "load_dotenv", lambda *_a, **_k: False)
    for nome in ("MYSQL_HOST", "MYSQL_PORT", "SEED", *VARIAVEIS):
        monkeypatch.delenv(nome, raising=False)
    for nome, valor in VARIAVEIS.items():
        monkeypatch.setenv(nome, valor)
    return monkeypatch


def test_padroes_validos(ambiente):
    s = config.load_settings()
    assert (s.host, s.port, s.seed) == ("127.0.0.1", 3306, 42)


@pytest.mark.parametrize("nome, valor", [("MYSQL_PORT", "abc"), ("MYSQL_PORT", "0"), ("MYSQL_PORT", "70000"),
                                          ("MYSQL_PORT", "3306; DROP"), ("SEED", "x"), ("SEED", "-1")])
def test_valores_invalidos_geram_erro_claro_sem_vazar_senha(ambiente, nome, valor):
    ambiente.setenv(nome, valor)
    with pytest.raises(RuntimeError) as erro:
        config.load_settings()
    assert nome in str(erro.value)
    assert VALOR_FALSO not in str(erro.value)


def test_variavel_obrigatoria_ausente(ambiente):
    ambiente.delenv("MYSQL_PASSWORD")
    with pytest.raises(RuntimeError, match="MYSQL_PASSWORD"):
        config.load_settings()


def _resultados(**sobras):
    base = {
        "coupon_summary": pd.DataFrame({"coupon_group": ["Com cupom", "Sem cupom"]}),
        "coupons": pd.DataFrame({"coupon": ["Sem cupom", "BLACK25"]}),
        "payments": pd.DataFrame({"payment_method": ["boleto", "pix"]}),
        **{nome: pd.DataFrame({"x": [1]}) for nome in ("categories", "abc", "channels", "states", "monthly", "rfm_segments")},
    }
    base.update(sobras)
    return SimpleNamespace(**base)


def test_relatorio_aceita_dados_completos():
    check_inputs(_resultados())


@pytest.mark.parametrize("ajuste, trecho", [
    ({"coupon_summary": pd.DataFrame({"coupon_group": ["Sem cupom"]})}, "com e sem cupom"),
    ({"coupons": pd.DataFrame({"coupon": ["Sem cupom"]})}, "algum cupom"),
    ({"payments": pd.DataFrame({"payment_method": ["pix"]})}, "boleto"),
    ({"abc": pd.DataFrame()}, "abc"),
])
def test_relatorio_recusa_dados_parciais_com_mensagem_clara(ajuste, trecho):
    with pytest.raises(RuntimeError, match=trecho):
        check_inputs(_resultados(**ajuste))
