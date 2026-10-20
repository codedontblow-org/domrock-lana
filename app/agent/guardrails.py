import re
import unicodedata
from rapidfuzz import fuzz, process

def normalizar(texto: str) -> str:
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"(.)\1{2,}", r"\1", texto) 
    return re.sub(r"\s+", " ", texto)


_PREFIXO = r"^(ola |oii |oi |hey |hi |bom dia |boa tarde |boa noite )?(lana[,\s]+)?"

PADROES_TRIVIAIS = [
    rf"{_PREFIXO}(oi|oii|ola|hey|hi|hello|bom dia|boa tarde|boa noite)[\s!.?]*$",
    rf"{_PREFIXO}(tudo bem|como vai|como voce esta)[\s!.?]*$",
    rf"{_PREFIXO}(obrigado|obrigada|valeu|thanks|thank you|vlw)[\s!.?]*$",
]

PADROES_AJUDA = [
    rf"{_PREFIXO}(o que (voce|vc) pode fazer|oq (voce|vc) pode fazer|"
    r"o que (voce|vc) faz|quais (sao )?suas funcoes|help|ajuda|me ajuda)[\s!.?]*$",
]

# Frases de referência para o fuzzy matching (o "gabarito")
REFERENCIAS_TRIVIAIS = [
    "oi", "ola", "hey", "hi", "hello",
    "bom dia", "boa tarde", "boa noite",
    "tudo bem", "como vai", "como voce esta",
    "obrigado", "obrigada", "valeu", "vlw", "thanks",
    "oi lana", "ola lana", "bom dia lana",
]

REFERENCIAS_AJUDA = [
    "o que voce pode fazer", "o que vc pode fazer", "oq vc pode fazer",
    "o que voce faz", "o que vc faz",
    "quais suas funcoes", "quais sao suas funcoes",
    "me ajuda", "ajuda", "help",
    "como voce funciona", "o que voce e",
]

LIMIAR_TRIVIAL = 88   # 0–100
LIMIAR_AJUDA = 85

MENSAGEM_TRIVIAL = (
    "Sou a Lana, assistente de estratégias de vendas. "
    "Posso ajudar com campanhas, comissionamento, análise de vendas e simulações. "
    "Me diga o que você precisa."
)

MENSAGEM_AJUDA = (
    "Posso ajudar com: criação e ajuste de campanhas, registro de parâmetros, "
    "análise de histórico de vendas, cálculo de riscos e simulações. "
    "Para começar, descreva sua campanha ou o que deseja analisar."
)


def _match_fuzzy(texto: str, referencias: list[str], limiar: float) -> bool:
    # process.extractOne devolve (match, score, index) ou None
    resultado = process.extractOne(texto, referencias, scorer=fuzz.ratio)
    return bool(resultado and resultado[1] >= limiar)


def classificar_guardrail(texto: str) -> str | None:
    texto_limpo = normalizar(texto)
    if not texto_limpo:
        return "trivial"

    # 1. Regex (rápido e determinístico)
    for padrao in PADROES_TRIVIAIS:
        if re.match(padrao, texto_limpo):
            return "trivial"
    for padrao in PADROES_AJUDA:
        if re.match(padrao, texto_limpo):
            return "ajuda"

    if len(texto_limpo) <= 2:
        return "trivial"

    # 2. Fuzzy (variações e typos)
    # Só roda no fuzzy se a mensagem for curta — evita classificar frases longas
    # (que normalmente têm contexto de negócio) por engano.
    if len(texto_limpo) <= 40:
        if _match_fuzzy(texto_limpo, REFERENCIAS_AJUDA, LIMIAR_AJUDA):
            return "ajuda"
        if _match_fuzzy(texto_limpo, REFERENCIAS_TRIVIAIS, LIMIAR_TRIVIAL):
            return "trivial"

    return None


def obter_resposta_guardrail(tipo: str) -> str | None:
    return {"trivial": MENSAGEM_TRIVIAL, "ajuda": MENSAGEM_AJUDA}.get(tipo)