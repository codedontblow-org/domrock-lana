import json
from typing import Any
from uuid import uuid4

from langchain_core.tools import tool

from app.tools.regra_tool.parametros import montar_regra

NOME_TOOL_REGRA = "registrar_parametros_regra"


# content_and_artifact: a LLM lê o JSON; o front recebe o dict intacto via ToolMessage.artifact.
@tool(NOME_TOOL_REGRA, response_format="content_and_artifact")
def registrar_parametros_regra(
    comando_original: str,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    pct_acrescimo: float | None = None,
    marcas_alvo: list[str] | None = None,
    cargos_alvo: list[str] | None = None,
    meta_vendas: float | None = None,
    orcamento_limite: float | None = None,
) -> tuple[str, dict[str, Any]]:
    """
    Registra os parâmetros de uma regra de campanha de comissionamento descrita pelo usuário.

    Use sempre que o usuário descrever ou alterar uma regra de campanha. Passe SOMENTE o que
    o usuário disse; NUNCA invente nem assuma valores padrão. Deixe ausente o que não foi dito.
    A resposta traz `faltantes`: pergunte ao usuário por cada um deles. Quando o usuário
    completar ou alterar algo, chame de novo com TODOS os valores já conhecidos da conversa.

    Args:
        comando_original: A frase do usuário que descreve a regra.
        data_inicio: Início da vigência em YYYY-MM-DD. Os dados disponíveis são de 2025.
        data_fim: Fim da vigência em YYYY-MM-DD.
        pct_acrescimo: Acréscimo em pontos percentuais sobre a comissão (+1% -> 1.0).
        marcas_alvo: Códigos de marca: "10" PRETO, "20" BRANCO, "30" AZUL, "40" VERMELHO,
            "50" AMARELO, "60" CINZA, ou ["ALL"] para todas.
        cargos_alvo: Códigos dos cargos que RECEBEM a regra: "100" VENDEDOR LOJA,
            "150" GERENTE, "200" VENDEDOR BALCAO, "300" ASSISTENTE DE VENDAS.
            "Todos exceto gerentes" -> ["100", "200", "300"].
        meta_vendas: Meta financeira de vendas da campanha em R$.
        orcamento_limite: Orçamento máximo do incentivo (custo extra de comissão) em R$.
    """
    valores = {
        "periodo": _periodo(data_inicio, data_fim),
        "pct_acrescimo": pct_acrescimo,
        "marcas_alvo": marcas_alvo,
        "cargos_alvo": cargos_alvo,
        "meta_vendas": meta_vendas,
        "orcamento_limite": orcamento_limite,
    }
    regra = montar_regra(valores, comando_original, f"draft-{uuid4().hex[:8]}")
    contrato = regra.model_dump(mode="json")
    return json.dumps({"faltantes": regra.faltantes, "regra": contrato}, ensure_ascii=False), contrato


def _periodo(data_inicio: str | None, data_fim: str | None) -> dict[str, str] | None:
    if data_inicio is None or data_fim is None:
        return None
    return {"data_inicio": data_inicio, "data_fim": data_fim}
