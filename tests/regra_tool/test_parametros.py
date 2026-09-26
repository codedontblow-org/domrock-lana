import pytest

from app.tools.regra_tool.parametros import RegraInvalidaError, ler_parametros, montar_regra

VALORES_BLACK_FRIDAY = {
    "periodo": {"data_inicio": "2025-11-24", "data_fim": "2025-11-30"},
    "pct_acrescimo": 1.0,
    "marcas_alvo": ["ALL"],
    "cargos_alvo": ["100", "200", "300"],
    "meta_vendas": 1_000_000,
    "orcamento_limite": 30_000,
}


def test_montar_regra_lista_faltantes_sem_assumir_padrao() -> None:
    regra = montar_regra({"pct_acrescimo": 1.0}, "+1% na black friday", "draft-1")

    assert regra.faltantes == [
        "periodo", "marcas_alvo", "cargos_alvo", "meta_vendas", "orcamento_limite",
    ]
    assert [p.value for p in regra.parametros if p.key == "meta_vendas"] == [None]


def test_montar_regra_preenche_rotulos_e_opcoes_do_catalogo() -> None:
    regra = montar_regra(VALORES_BLACK_FRIDAY, "cmd", "draft-1")
    marcas = next(p for p in regra.parametros if p.key == "marcas_alvo")

    assert regra.faltantes == []
    assert marcas.type == "multi_select"
    assert marcas.options is not None and marcas.options[0].id == "ALL"


def test_ler_parametros_expande_todas_as_marcas() -> None:
    parametros = ler_parametros(montar_regra(VALORES_BLACK_FRIDAY, "cmd", "draft-1"))

    assert parametros.marcas_alvo == ["10", "20", "30", "40", "50", "60"]
    assert parametros.cargos_alvo == ["100", "200", "300"]
    assert str(parametros.data_inicio) == "2025-11-24"


@pytest.mark.parametrize(
    ("key", "valor", "trecho_erro"),
    [
        ("periodo", {"data_inicio": "2025-11-30", "data_fim": "2025-11-24"}, "depois de"),
        ("pct_acrescimo", -1, "maior que zero"),
        ("pct_acrescimo", "abc", "esperado número"),
        ("marcas_alvo", ["99"], "['99']"),
        ("orcamento_limite", None, "obrigatório"),
        ("periodo", {"data_inicio": "2025-11-24", "data_fim": None}, "YYYY-MM-DD"),
        ("cargos_alvo", {"id": "100"}, "esperado lista"),
    ],
)
def test_ler_parametros_rejeita_valor_invalido_com_o_valor_na_mensagem(
    key: str, valor: object, trecho_erro: str
) -> None:
    regra = montar_regra({**VALORES_BLACK_FRIDAY, key: valor}, "cmd", "draft-1")

    with pytest.raises(RegraInvalidaError) as erro:
        ler_parametros(regra)

    assert trecho_erro in str(erro.value)
    assert erro.value.erros[0].startswith(key)


@pytest.mark.parametrize("valor", ["30", 30])
def test_ler_parametros_aceita_codigo_solto_como_lista(valor: object) -> None:
    regra = montar_regra({**VALORES_BLACK_FRIDAY, "marcas_alvo": valor}, "cmd", "draft-1")

    assert ler_parametros(regra).marcas_alvo == ["30"]


def test_montar_regra_mantem_data_parcial_e_marca_periodo_como_faltante() -> None:
    periodo = {"data_inicio": "2025-11-24", "data_fim": None}

    regra = montar_regra({**VALORES_BLACK_FRIDAY, "periodo": periodo}, "cmd", "draft-1")

    assert regra.faltantes == ["periodo"]
    assert regra.parametros[0].value == periodo
