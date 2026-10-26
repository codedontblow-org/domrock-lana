from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.simulacao.explicacao import TEXTO_PADRAO, ExplicadorLlm
from app.simulacao.texto_humano import cliches_encontrados, fatos_da_simulacao, formatar_reais

RESUMO = {
    "totais": {"baseline": 338279.62, "simulado": 339947.96, "diferenca": 1668.34, "diferenca_pct": 0.49},
    "orcamento": {"orcamento_limite": 1000.0, "custo_incremental": 1668.34, "folga": -668.34, "cabe_no_orcamento": False},
    "meta": {"meta_vendas": 1500000.0, "vendas_periodo": 333666.01, "pct_atingimento": 22.24, "atingida": False},
    "por_marca": [{"codigo": "30", "baseline": 1, "simulado": 2, "diferenca": 1668.34}],
    "por_cargo": [{"codigo": "300", "baseline": 1, "simulado": 2, "diferenca": 1653.37},
                  {"codigo": "100", "baseline": 1, "simulado": 2, "diferenca": 14.97}],
}
TEXTO_LIMPO = (
    "Passa R$ 668,34 do orçamento de R$ 1.000,00. Todo o custo extra vem da marca Azul, quase todo "
    "com assistentes de vendas. Como a meta ficou em 22%, vale reduzir o acréscimo ou o público."
)
TEXTO_COM_CLICHE = "Olá, prezado gerente! Apresento com grande otimismo os resultados da nossa simulação. 📊"


class FakeModeloQueQuebra(FakeListChatModel):
    def invoke(self, *args, **kwargs):  # type: ignore[override]
        raise RuntimeError("429")


def test_cliches_encontrados_pega_os_vicios_de_texto_de_ia() -> None:
    achados = cliches_encontrados("Apresento, com otimismo e atenção aos detalhes, os resultados. 🚀")

    assert {"apresento", "otimis", "emoji"} <= set(achados)
    assert cliches_encontrados(TEXTO_LIMPO) == []


def test_fatos_escrevem_os_numeros_em_portugues() -> None:
    fatos = " ".join(fatos_da_simulacao(RESUMO))

    assert "Não cabe no orçamento de R$ 1.000,00; passa R$ 668,34." in fatos
    assert "marca Azul (100% do total)" in fatos and "assistente de vendas (99% do total)" in fatos
    assert formatar_reais(1234567.891) == "R$ 1.234.567,89"


def test_explicar_aceita_texto_sem_cliche_de_primeira() -> None:
    modelo = FakeListChatModel(responses=[TEXTO_LIMPO])

    assert ExplicadorLlm(modelo).explicar(RESUMO) == TEXTO_LIMPO


def test_explicar_pede_reescrita_quando_vem_cliche() -> None:
    modelo = FakeListChatModel(responses=[TEXTO_COM_CLICHE, TEXTO_LIMPO])

    assert ExplicadorLlm(modelo).explicar(RESUMO) == TEXTO_LIMPO


def test_explicar_usa_os_numeros_quando_a_llm_insiste_no_cliche() -> None:
    modelo = FakeListChatModel(responses=[TEXTO_COM_CLICHE, TEXTO_COM_CLICHE])

    texto = ExplicadorLlm(modelo).explicar(RESUMO)

    assert texto.startswith("No histórico, as vendas desse período somaram R$ 333.666,01")
    assert cliches_encontrados(texto) == []


def test_explicar_nao_derruba_a_simulacao_quando_a_llm_falha() -> None:
    assert ExplicadorLlm(FakeModeloQueQuebra(responses=["x"])).explicar(RESUMO) == TEXTO_PADRAO


def test_fato_da_meta_e_historico_e_nao_diz_superou_em_120() -> None:
    meta = {"meta_vendas": 2000000.0, "vendas_periodo": 2406125.93, "pct_atingimento": 120.31, "atingida": True}

    fatos = " ".join(fatos_da_simulacao({**RESUMO, "meta": meta}))

    assert "No histórico, as vendas desse período somaram R$ 2.406.125,93, 120% da meta" in fatos
    assert "(20% acima da meta)" in fatos and "batida" not in fatos


def test_fatos_trazem_pessoas_loja_e_cenarios_calculados() -> None:
    resumo = {
        **RESUMO,
        "impacto": {"pessoas_impactadas": 12, "pessoas_total": 40, "media_por_pessoa": 139.03, "maior_acrescimo": 480.0},
        "maiores_lojas": [{"codigo": "13", "baseline": 1, "simulado": 2, "diferenca": 834.17}],
        "cenarios": [{"tipo": "ajustar_acrescimo", "titulo": "Acréscimo menor, dentro do orçamento",
                      "pct_acrescimo": 0.29, "marcas_alvo": ["30"], "custo_incremental": 967.64,
                      "economia": 700.7, "cabe_no_orcamento": True}],
    }

    fatos = " ".join(fatos_da_simulacao(resumo))

    assert "12 de 40 pessoas recebem o acréscimo, em média R$ 139,03 cada" in fatos
    assert "loja 13, R$ 834,17 (50% do total)" in fatos
    assert "acréscimo de 0,29%, custo extra R$ 967,64, cabe no orçamento" in fatos


# Critério do A6-72: Black Friday +1%, meta de R$ 2 milhões, venda de R$ 2.406.125,93.
META_BF = {"meta_vendas": 2000000.0, "vendas_periodo": 2406125.93, "pct_atingimento": 120.31, "atingida": True,
           "diferenca": 406125.93}
RESUMO_BF = {
    **RESUMO,
    "totais": {"baseline": 480263.24, "simulado": 503999.34, "diferenca": 23736.10, "diferenca_pct": 4.94},
    "meta": META_BF,
    "retorno": {"provisorio": True, "custo_pct_venda": 0.99, "custo_por_real_acima_meta": 0.06},
    "orcamento": {"orcamento_limite": 20000.0, "custo_incremental": 23736.10, "folga": -3736.10, "cabe_no_orcamento": False},
}
SEM_ORCAMENTO = {
    **RESUMO_BF, "orcamento": None,
    "cenarios": [{"tipo": "sem_marca", "titulo": "Sem a marca Preto", "pct_acrescimo": 1.0, "marcas_alvo": ["30"],
                  "custo_incremental": 4398.28, "economia": 19337.82, "cabe_no_orcamento": None}],
}


def test_fatos_seguem_a_ordem_meta_comissao_retorno_orcamento() -> None:
    fatos = " ".join(fatos_da_simulacao(RESUMO_BF))

    posicoes = [fatos.index(t) for t in ("No histórico", "Custo extra", "Retorno", "Não cabe no orçamento")]
    assert posicoes == sorted(posicoes)


def test_fato_da_meta_traz_a_diferenca_em_reais() -> None:
    fatos = " ".join(fatos_da_simulacao(RESUMO_BF))

    assert "R$ 406.125,93 acima da meta" in fatos


def test_fato_do_retorno_e_provisorio_e_usa_os_numeros_calculados() -> None:
    fatos = " ".join(fatos_da_simulacao(RESUMO_BF))

    assert "Retorno (conta provisória): o custo extra é 0,99% da venda do período" in fatos
    assert "R$ 0,06 para cada R$ 1 vendido acima da meta" in fatos


def test_abaixo_da_meta_o_retorno_nao_fala_de_venda_acima_dela() -> None:
    meta = {**META_BF, "meta_vendas": 3000000.0, "pct_atingimento": 80.2, "atingida": False, "diferenca": -593874.07}
    retorno = {"provisorio": True, "custo_pct_venda": 0.99, "custo_por_real_acima_meta": None}

    fatos = " ".join(fatos_da_simulacao({**RESUMO_BF, "meta": meta, "retorno": retorno}))

    assert "R$ 593.874,07 abaixo da meta" in fatos and "para cada R$ 1" not in fatos


def test_sem_orcamento_os_fatos_nao_citam_orcamento() -> None:
    fatos = " ".join(fatos_da_simulacao(SEM_ORCAMENTO)).lower()

    assert "orçamento" not in fatos and "sem a marca preto" in fatos


def test_explicar_sem_orcamento_redige_com_a_llm_e_nao_cai_no_texto_padrao() -> None:
    modelo = FakeListChatModel(responses=[TEXTO_LIMPO])

    assert ExplicadorLlm(modelo).explicar(SEM_ORCAMENTO) == TEXTO_LIMPO
