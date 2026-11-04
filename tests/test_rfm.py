import pandas as pd
import pytest

from aurora.analysis.rfm import assign_segment, frequency_score, score_rfm, summarize_segments


def _base(n=20):
    return pd.DataFrame({
        "customer_id": range(1, n + 1),
        "last_order_date": pd.date_range("2025-01-01", periods=n, freq="7D"),
        "frequency": [1] * (n - 5) + [2, 3, 4, 5, 8],
        "monetary": [50.0 * (i + 1) for i in range(n)],
    })


def test_notas_ficam_entre_1_e_5():
    scored = score_rfm(_base())
    for coluna in ("r_score", "f_score", "m_score"):
        assert scored[coluna].between(1, 5).all(), coluna


def test_recencia_mais_recente_recebe_nota_maior():
    scored = score_rfm(_base()).set_index("customer_id")
    assert scored.loc[20, "r_score"] == 5
    assert scored.loc[1, "r_score"] == 1


def test_valor_maior_recebe_nota_maior():
    scored = score_rfm(_base()).set_index("customer_id")
    assert scored.loc[20, "m_score"] == 5
    assert scored.loc[1, "m_score"] == 1


def test_quintis_tem_tamanhos_balanceados_mesmo_com_empates():
    base = _base(50)
    base["monetary"] = 100.0  # todos iguais: empates totais
    scored = score_rfm(base)
    assert scored["m_score"].value_counts().tolist() == [10] * 5


def test_frequencia_por_faixas_fixas():
    assert frequency_score(pd.Series([1, 2, 3, 4, 5, 9])).tolist() == [1, 2, 3, 4, 5, 5]


def test_segmentos_regras_principais():
    r = pd.Series([5, 3, 5, 3, 1, 1])
    f = pd.Series([5, 3, 1, 1, 4, 1])
    assert assign_segment(r, f).tolist() == [
        "Campeões", "Fiéis", "Promissores", "Precisam de atenção", "Em risco", "Hibernando"]


def test_data_de_referencia_explicita_define_recencia():
    base = _base()
    scored = score_rfm(base, reference_date=pd.Timestamp("2026-01-01"))
    ultimo = scored.set_index("customer_id").loc[20]
    esperado = (pd.Timestamp("2026-01-01") - base.loc[19, "last_order_date"]).days
    assert ultimo["recency_days"] == pytest.approx(esperado)


def test_entrada_nao_e_modificada():
    base = _base()
    copia = base.copy()
    score_rfm(base)
    pd.testing.assert_frame_equal(base, copia)


def test_valida_colunas_e_tamanho_minimo():
    with pytest.raises(ValueError, match="Colunas ausentes"):
        score_rfm(_base().drop(columns=["monetary"]))
    with pytest.raises(ValueError, match="ao menos 5"):
        score_rfm(_base().head(4))


def test_resumo_soma_100_por_cento():
    resumo = summarize_segments(score_rfm(_base(100)))
    assert resumo["customer_share_pct"].sum() == pytest.approx(100)
    assert resumo["revenue_share_pct"].sum() == pytest.approx(100)
    assert resumo["customers"].sum() == 100
