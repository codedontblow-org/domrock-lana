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

    assert texto.startswith("Custo extra da campanha: R$ 1.668,34")
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
