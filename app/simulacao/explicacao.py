"""Explicação em linguagem natural do resultado já apurado.

A LLM só redige: recebe os números prontos, em frases, e não pode calcular nem inventar valores.
Se a LLM falhar, a simulação continua com um texto padrão; o número nunca depende dela.

Contra texto com "cara de IA" (pedido do time: "com grande otimismo mas mantendo a atenção
necessária", "apresento os resultados…"):
1. o prompt pede conclusão primeiro, fala de colega e proíbe anunciar o próprio tom;
2. `cliches_encontrados` confere a resposta; havendo clichê, a LLM reescreve uma vez sabendo quais;
3. se insistir, as frases com clichê saem; se sobrar pouco, usa o resumo determinístico.
"""
from typing import Protocol

from langchain_core.runnables import Runnable

from app.core.config import extract_text
from app.simulacao.texto_humano import (
    cliches_encontrados, fatos_da_simulacao, remover_frases_com_cliche, resumo_deterministico,
)

TEXTO_PADRAO = "Simulação concluída. Veja os totais e o veredito de orçamento abaixo."
MINIMO_CARACTERES = 120

PROMPT_EXPLICACAO = """Você é Lana, analista de campanhas de vendas, comentando uma simulação com
o gerente que a pediu, como uma colega de trabalho faria numa conversa rápida.

Fatos (use só estes números, exatamente como estão escritos):
{fatos}

Como escrever:
- A primeira frase já dá a conclusão: cabe ou não no orçamento, com o valor.
- Depois, em 2 ou 3 frases, diga o que mais pesa no custo e sugira UM dos cenários calculados
  que estão nos fatos, com o percentual e o custo dele. Nunca invente outro percentual ou valor.
- Vendas do período são histórico: não diga que a meta "foi batida" nem "vai ser atingida".
- Frases curtas e diretas, em português do Brasil, sem Markdown de título e sem listas.
- Seja otimista quando os números permitem e aponte o risco quando existe, mas NUNCA descreva
  o seu tom ou atitude ("com otimismo", "com atenção", "com cautela").
- Não cumprimente, não se apresente, não diga "apresento", "segue", "nossa simulação".
- Não use: vale ressaltar, é importante, crucial, fundamental, alavancar, impulsionar, otimizar,
  potencializar, jornada, excelente, incrível, folga negativa, emojis.

Exemplo do tom certo (números de outra campanha, não copie):
Estoura o orçamento de R$ 10.000,00 em R$ 2.140,00. Quase todo o custo vem da marca Preto, que
concentra 81% do acréscimo, puxado pelos vendedores de loja. Com acréscimo de 0,82% a campanha
custa R$ 9.980,00 e cabe; outra saída é tirar a marca Preto, que baixa o custo para R$ 2.300,00.
{correcao}"""

CORRECAO = "\nSua versão anterior usou expressões proibidas ({cliches}). Reescreva sem elas."


class Explicador(Protocol):
    def explicar(self, resumo: dict[str, object]) -> str: ...


class ExplicadorLlm:
    """Ex.: ExplicadorLlm(get_ai_model()).explicar({"totais": {...}, "orcamento": {...}, ...})"""

    def __init__(self, modelo: Runnable) -> None:
        self._modelo = modelo

    def explicar(self, resumo: dict[str, object]) -> str:
        try:
            return self._explicar_sem_cliche(resumo)
        except Exception:  # explicação é acessória; falha da LLM não derruba a simulação
            return TEXTO_PADRAO

    def _explicar_sem_cliche(self, resumo: dict) -> str:
        fatos = "\n".join(f"- {fato}" for fato in fatos_da_simulacao(resumo))
        texto = self._redigir(fatos, correcao="")
        cliches = cliches_encontrados(texto)
        if cliches:
            texto = self._redigir(fatos, correcao=CORRECAO.format(cliches=", ".join(cliches)))
        return _limpar_ou_resumir(texto, resumo)

    def _redigir(self, fatos: str, correcao: str) -> str:
        return extract_text(self._modelo.invoke(PROMPT_EXPLICACAO.format(fatos=fatos, correcao=correcao)))


def _limpar_ou_resumir(texto: str, resumo: dict) -> str:
    """Tira as frases com clichê; se sobrar pouco, o texto vem só dos números."""
    limpo = remover_frases_com_cliche(texto) if cliches_encontrados(texto) else texto.strip()
    return limpo if len(limpo) >= MINIMO_CARACTERES else resumo_deterministico(resumo)
