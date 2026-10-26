"""Trilha do chat (contrato 2.2 e 3.1): um passo por ferramenta chamada no turno.

Tudo sai das chamadas (`AIMessage.tool_calls`) e dos retornos (`ToolMessage`) das ferramentas. O texto
que a LLM escreve antes de chamar uma ferramenta não entra: no A6-70 ele virava a descrição do passo
e às vezes vazava como resposta (era o "pensamento" dela).

Ex.: montar_trilha_chat(mensagens_do_turno, "gemini-3.5-flash-lite")["passos"][0]["ferramenta"] -> "consultar_banco"
"""
import ast
import json
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolCall, ToolMessage
from pydantic import BaseModel

from app.core.trilha import PassoTrilha, competencias_por_extenso
from app.tools.regra_tool.tool import NOME_TOOL_REGRA

NOME_TOOL_CONSULTA = "consultar_banco"

# `status` do consultar_banco (QueryResponseBody) -> descrição do passo que falhou
FALHAS_CONSULTA = {
    "recusado": "Consulta recusada: o dado não existe no banco",
    "bloqueado": "Consulta bloqueada pela checagem de segurança",
    "erro_geracao": "Falha ao montar a consulta",
    "erro_execucao": "Falha ao executar a consulta no banco",
}

# Retorno com Decimal('1.5'), como o LangChain serializa às vezes o dict da ferramenta
DECIMAL_PYTHON = re.compile(r"Decimal\((['\"]?)([0-9.-]+)\1\)")


class TrilhaChat(BaseModel):
    """`trilha` da resposta do chat: sem tentativas nem premissas, que são da simulação."""

    modelo: str
    tentativas: int | None = None
    premissas: list[str] = []
    passos: list[PassoTrilha]


def montar_trilha_chat(messages: list[BaseMessage], modelo_padrao: str) -> dict[str, Any] | None:
    """Trilha do turno, ou None quando a Lana respondeu sem usar ferramenta (contrato 2.2)."""
    chamadas = [chamada for m in messages if isinstance(m, AIMessage) for chamada in m.tool_calls]
    if not chamadas:
        return None
    retornos = {m.tool_call_id: m for m in messages if isinstance(m, ToolMessage)}
    passos = [_passo(ordem, chamada, retornos.get(chamada["id"])) for ordem, chamada in enumerate(chamadas, start=1)]
    return TrilhaChat(modelo=_modelo_usado(messages, modelo_padrao), passos=passos).model_dump(mode="json")


def _modelo_usado(messages: list[BaseMessage], modelo_padrao: str) -> str:
    # Com a cadeia de fallback (AI_FALLBACKS), quem respondeu pode não ser o AI_MODEL.
    for m in reversed(messages):
        nome = m.response_metadata.get("model_name") if isinstance(m, AIMessage) else None
        if nome:
            return str(nome)
    return modelo_padrao


def _passo(ordem: int, chamada: ToolCall, retorno: ToolMessage | None) -> PassoTrilha:
    nome = chamada["name"]
    if retorno is None:
        return PassoTrilha(ordem=ordem, ferramenta=nome, descricao="A ferramenta não devolveu resultado",
                           situacao="ERRO", mensagem_erro=f"Sem retorno para a chamada {chamada['id']}")
    resultado = ler_retorno_da_ferramenta(retorno.content)
    if nome == NOME_TOOL_CONSULTA:
        return _passo_consulta(ordem, resultado)
    if nome == NOME_TOOL_REGRA:
        return _passo_regra(ordem, resultado)
    return _passo_generico(ordem, nome, resultado)


def _passo_consulta(ordem: int, resultado: dict[str, Any]) -> PassoTrilha:
    tabelas = list(resultado.get("tabelas") or [])
    competencias = list(resultado.get("competencias") or [])
    comum = {
        "ordem": ordem, "ferramenta": NOME_TOOL_CONSULTA, "tabelas_acessadas": tabelas,
        "competencias": competencias, "filtros": texto_dos_filtros(resultado.get("filtros")),
        "sql_executado": resultado.get("sql") or resultado.get("sql_gerado"),
        "tempo_ms": _inteiro(resultado.get("tempo")),
    }
    status = resultado.get("status")
    if status != "sucesso":
        mensagem = resultado.get("motivo") or resultado.get("mensagem") or f"Consulta terminou em {status!r}"
        descricao = FALHAS_CONSULTA.get(str(status), "Falha na consulta ao banco")
        return PassoTrilha(**comum, descricao=descricao, situacao="ERRO", mensagem_erro=str(mensagem))
    dados = list(resultado.get("dados") or [])
    return PassoTrilha(**comum, descricao=_descricao_consulta(tabelas, competencias, len(dados)),
                       registros_retornados=len(dados), dados=dados)


def _descricao_consulta(tabelas: list[str], competencias: list[str], registros: int) -> str:
    """Ex.: _descricao_consulta(["venda"], ["2025-10"], 1) -> "Consulta em venda de out/2025: 1 registro" """
    onde = f"Consulta em {', '.join(tabelas)}" if tabelas else "Consulta ao banco"
    quando = f" de {competencias_por_extenso(competencias)}" if competencias else ""
    return f"{onde}{quando}: {registros} {'registro' if registros == 1 else 'registros'}"


def _passo_regra(ordem: int, resultado: dict[str, Any]) -> PassoTrilha:
    comum = {
        "ordem": ordem, "ferramenta": NOME_TOOL_REGRA,
        "competencias": list(resultado.get("competencias") or []),
        "filtros": texto_dos_filtros(resultado.get("filtros")), "tempo_ms": _inteiro(resultado.get("tempo")),
    }
    if resultado.get("situacao") != "ok":
        return PassoTrilha(**comum, descricao="Falha ao registrar a ficha da campanha", situacao="ERRO",
                           mensagem_erro=str(resultado.get("situacao") or "sem detalhe"))
    return PassoTrilha(**comum, descricao=_descricao_regra(resultado))


def _descricao_regra(resultado: dict[str, Any]) -> str:
    """Ex.: com faltantes ["meta_vendas"] -> "Ficha da campanha registrada; falta informar: Meta de vendas" """
    parametros = (resultado.get("regra") or {}).get("parametros") or []
    rotulos = {p.get("key"): p.get("label") for p in parametros if isinstance(p, dict)}
    faltantes = [str(rotulos.get(chave) or chave) for chave in resultado.get("faltantes") or []]
    if not faltantes:
        return "Ficha da campanha registrada"
    return f"Ficha da campanha registrada; falta informar: {', '.join(faltantes)}"


def _passo_generico(ordem: int, nome: str, resultado: dict[str, Any]) -> PassoTrilha:
    situacao = resultado.get("situacao", "ok")
    if situacao == "ok":
        return PassoTrilha(ordem=ordem, ferramenta=nome, descricao="Ferramenta executada",
                           tempo_ms=_inteiro(resultado.get("tempo")))
    return PassoTrilha(ordem=ordem, ferramenta=nome, descricao="Falha ao executar a ferramenta",
                       situacao="ERRO", mensagem_erro=str(situacao))


def texto_dos_filtros(filtros: object) -> str | None:
    """Filtros como texto (contrato 2.2). Ex.: texto_dos_filtros({"marcas": ["10"], "cargos": None}) -> "marcas: 10" """
    if filtros is None or isinstance(filtros, str):
        return filtros or None
    if isinstance(filtros, dict):
        partes = [f"{chave}: {texto_dos_filtros(valor)}" for chave, valor in filtros.items() if valor]
        return "; ".join(partes) or None
    if isinstance(filtros, list):
        return ", ".join(str(item) for item in filtros) or None
    return str(filtros)


def _inteiro(valor: object) -> int:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return 0
    return int(round(valor))


def ler_retorno_da_ferramenta(conteudo: object) -> dict[str, Any]:
    """O retorno da ferramenta como dict: JSON, ou o repr Python com Decimal que o LangChain às vezes manda.

    Ex.: ler_retorno_da_ferramenta("{'status': 'sucesso', 'total': Decimal('1.5')}")["total"] -> 1.5
    """
    if isinstance(conteudo, dict):
        return conteudo
    if not isinstance(conteudo, str):
        return {}
    for ler in (json.loads, _json_sem_decimal, _literal_sem_decimal):
        try:
            lido = ler(conteudo)
        except (ValueError, SyntaxError, TypeError):
            continue
        return lido if isinstance(lido, dict) else {}
    return {}


def _json_sem_decimal(conteudo: str) -> object:
    return json.loads(DECIMAL_PYTHON.sub(r"\2", conteudo))


def _literal_sem_decimal(conteudo: str) -> object:
    return ast.literal_eval(DECIMAL_PYTHON.sub(r"\2", conteudo))
