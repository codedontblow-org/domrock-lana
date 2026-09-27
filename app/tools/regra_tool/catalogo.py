"""Dicionário de metadados dos parâmetros da regra.

Fonte: docs-camplana/informacoes_uteis/estrutura_parametros_regra.txt. O front renderiza
cada parâmetro pelo `type`; a LLM só preenche valores, nunca rótulos nem opções.
"""
from app.tools.regra_tool.dtos import OpcaoParametro

TODAS_AS_MARCAS = "ALL"

OPCOES_MARCAS: list[OpcaoParametro] = [
    OpcaoParametro(id=TODAS_AS_MARCAS, label="Todas as Marcas"),
    OpcaoParametro(id="10", label="PRETO (10)"),
    OpcaoParametro(id="20", label="BRANCO (20)"),
    OpcaoParametro(id="30", label="AZUL (30)"),
    OpcaoParametro(id="40", label="VERMELHO (40)"),
    OpcaoParametro(id="50", label="AMARELO (50)"),
    OpcaoParametro(id="60", label="CINZA (60)"),
]

# Cargo 150 cobre GERENTE DE LOJA e GERENTE QUIOSQUE (decisão do cliente: gerente é gerente).
OPCOES_CARGOS: list[OpcaoParametro] = [
    OpcaoParametro(id="100", label="VENDEDOR LOJA"),
    OpcaoParametro(id="150", label="GERENTE"),
    OpcaoParametro(id="200", label="VENDEDOR BALCAO"),
    OpcaoParametro(id="300", label="ASSISTENTE DE VENDAS"),
]

CODIGOS_MARCA: frozenset[str] = frozenset(o.id for o in OPCOES_MARCAS)
CODIGOS_CARGO: frozenset[str] = frozenset(o.id for o in OPCOES_CARGOS)

# key -> (label, type, categoria)
METADADOS: dict[str, tuple[str, str, str]] = {
    "periodo": ("Prazo da Campanha", "date_range", "REGRA"),
    "pct_acrescimo": ("Acréscimo de Comissão (%)", "percentage", "REGRA"),
    "marcas_alvo": ("Marcas Participantes", "multi_select", "REGRA"),
    "cargos_alvo": ("Cargos Elegíveis", "multi_select", "REGRA"),
    "meta_vendas": ("Meta Financeira da Campanha (R$)", "currency", "CONSTRAINT"),
    "orcamento_limite": ("Orçamento Máximo de Incentivo (R$)", "currency", "CONSTRAINT"),
}

OPCOES_POR_CHAVE: dict[str, list[OpcaoParametro]] = {
    "marcas_alvo": OPCOES_MARCAS,
    "cargos_alvo": OPCOES_CARGOS,
}
