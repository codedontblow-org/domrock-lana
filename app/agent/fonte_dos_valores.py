"""Número sem fonte não é apresentado como fato (A6-70, critério "a consulta ao banco falhou").

Um valor em reais na resposta só passa se o turno teve uma consulta com sucesso, ou se o valor já
estava no que o usuário escreveu, na ficha (orçamento, meta) ou na conversa até aqui. Senão, a
resposta inteira é trocada por um aviso fixo, sem valor em reais.

Ex.: conferir_fonte_dos_valores("A marca 30 vendeu R$ 333.666,01.", trilha_com_erro, [], []) -> RESPOSTA_SEM_FONTE
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agent.trilha import NOME_TOOL_CONSULTA

RESPOSTA_SEM_FONTE = (
    "Não encontrei na base uma consulta que sustente esse valor, então não vou apresentá-lo como fato. "
    "Pergunte de novo que eu refaço a consulta."
)

# "R$ 333.666,01", "R$ 2 milhões", "R$ 2,4 mi"
VALOR_EM_REAIS = re.compile(
    r"R\$\s*(\d[\d.]*(?:,\d+)?)(?:\s*(mil|milh(?:ão|ões|ao|oes)|mi|bilh(?:ão|ões|ao|oes)|bi)\b)?",
    re.IGNORECASE,
)
CENTAVO = Decimal("0.01")


def conferir_fonte_dos_valores(
    resposta: str, trilha: dict[str, Any] | None, textos_conhecidos: list[str],
    fichas: list[dict[str, Any] | None],
) -> str:
    """A resposta como veio, ou RESPOSTA_SEM_FONTE quando cita reais sem fonte."""
    valores = valores_em_reais(resposta)
    if not valores or _consultou_com_sucesso(trilha):
        return resposta
    conhecidos = set().union(*(valores_em_reais(texto) for texto in textos_conhecidos), _valores_das_fichas(fichas))
    return resposta if valores <= conhecidos else RESPOSTA_SEM_FONTE


def valores_em_reais(texto: str) -> set[Decimal]:
    """Ex.: valores_em_reais("meta de R$ 2 milhões e R$ 1.234,50") -> {Decimal("2000000.00"), Decimal("1234.50")}"""
    valores = set()
    for numero, escala in VALOR_EM_REAIS.findall(texto):
        valor = _decimal_brasileiro(numero)
        if valor is not None:
            valores.add((valor * _multiplicador(escala)).quantize(CENTAVO))
    return valores


def _decimal_brasileiro(numero: str) -> Decimal | None:
    try:
        return Decimal(numero.rstrip(".").replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def _multiplicador(escala: str) -> int:
    """Ex.: _multiplicador("milhões") -> 1_000_000; _multiplicador("") -> 1"""
    escala = escala.lower()
    if escala == "mil":
        return 1_000
    if escala.startswith("mi"):
        return 1_000_000
    return 1_000_000_000 if escala.startswith("bi") else 1


def _consultou_com_sucesso(trilha: dict[str, Any] | None) -> bool:
    passos = (trilha or {}).get("passos") or []
    return any(p["ferramenta"] == NOME_TOOL_CONSULTA and p["situacao"] == "SUCESSO" for p in passos)


def _valores_das_fichas(fichas: list[dict[str, Any] | None]) -> set[Decimal]:
    valores = set()
    for ficha in fichas:
        for parametro in (ficha or {}).get("parametros") or []:
            valor = parametro.get("value")
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                valores.add(Decimal(str(valor)).quantize(CENTAVO))
    return valores
