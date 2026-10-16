import re
import unicodedata

def normalizar(texto: str) -> str:
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto)

# Prefixos opcionais que o usuário costuma colocar antes da pergunta
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

def classificar_guardrail(texto: str) -> str | None:
    texto_limpo = normalizar(texto)
    if not texto_limpo:
        return "trivial"

    for padrao in PADROES_TRIVIAIS:
        if re.match(padrao, texto_limpo):
            return "trivial"

    for padrao in PADROES_AJUDA:
        if re.match(padrao, texto_limpo):
            return "ajuda"

    if len(texto_limpo) <= 2:
        return "trivial"

    return None

def obter_resposta_guardrail(tipo: str) -> str | None:
    return {"trivial": MENSAGEM_TRIVIAL, "ajuda": MENSAGEM_AJUDA}.get(tipo)