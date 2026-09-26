"""Explicação em linguagem natural do resultado já apurado.

A LLM só redige: recebe os números prontos e não pode calcular nem inventar valores.
Se a LLM falhar, a simulação continua com um texto padrão; o número nunca depende dela.
"""
import json
from typing import Protocol

from langchain_core.language_models import BaseChatModel

from app.core.config import extract_text

TEXTO_PADRAO = "Simulação concluída. Veja os totais e o veredito de orçamento abaixo."

PROMPT_EXPLICACAO = """Redija, em até 5 frases, em português formal e objetivo e em Markdown, a
leitura do resultado desta simulação de campanha para um gerente de vendas. Sem cumprimento,
sem emojis e sem expressões de entusiasmo. Use SOMENTE os números abaixo, sem recalcular nem
inventar valores. Diga se cabe no orçamento, se a meta foi atingida e onde o custo se concentra.
Escreva dinheiro como R$ 23.736,17 e percentuais como 4,94%. Folga negativa é quanto passa do
orçamento. Códigos de marca: 10 Preto, 20 Branco, 30 Azul, 40 Vermelho, 50 Amarelo, 60 Cinza.
Códigos de cargo: 100 vendedor loja, 150 gerente, 200 vendedor balcão, 300 assistente de vendas.

{resultado}
"""


class Explicador(Protocol):
    def explicar(self, resumo: dict[str, object]) -> str: ...


class ExplicadorLlm:
    """Ex.: ExplicadorLlm(get_ai_model()).explicar({"totais": {...}})"""

    def __init__(self, modelo: BaseChatModel) -> None:
        self._modelo = modelo

    def explicar(self, resumo: dict[str, object]) -> str:
        prompt = PROMPT_EXPLICACAO.format(resultado=json.dumps(resumo, ensure_ascii=False, indent=2))
        try:
            return extract_text(self._modelo.invoke(prompt)) or TEXTO_PADRAO
        except Exception:  # explicação é acessória; falha da LLM não derruba a simulação
            return TEXTO_PADRAO
