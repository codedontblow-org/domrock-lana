"""Texto da explicação sem "cara de IA".

Três peças usadas por `explicacao.py`:
- `fatos_da_simulacao`: os números já escritos em português (R$ 1.668,34; 22% da meta), para a
  LLM só redigir, sem despejar JSON cru nem inventar formatação;
- `cliches_encontrados`: expressões típicas de texto gerado ("com otimismo e atenção", "apresento
  os resultados", "vale ressaltar") que o time pediu para eliminar;
- `resumo_deterministico`: texto montado só com os números, usado quando a LLM insiste nos clichês.
"""
import re
import unicodedata

NOMES_MARCA = {"10": "Preto", "20": "Branco", "30": "Azul", "40": "Vermelho", "50": "Amarelo", "60": "Cinza"}
NOMES_CARGO = {"100": "vendedor loja", "150": "gerente", "200": "vendedor balcão", "300": "assistente de vendas"}

# Padrões sem acento e em minúsculas (o texto é normalizado antes da busca).
PADROES_CLICHE = (
    r"otimis", r"atencao (aos detalhes|necessaria)", r"apresento", r"com grande", r"prezad",
    r"aqui e a lana", r"\bola\b", r"vale (ressaltar|destacar|a pena)", r"e importante (destacar|ressaltar|notar)",
    r"em suma", r"crucial", r"fundamental", r"jornada", r"alavanc", r"potencializ", r"impulsion",
    r"sinergi", r"otimizar", r"folga negativa", r"cenario desafiador", r"excelente", r"incrivel",
    r"com certeza", r"nao hesite", r"a disposicao", r"espero ter ajudado", r"vamos juntos",
    r"mantendo a atencao", r"com cautela e", r"otimos resultados", r"de forma estrategica", r"nossa simulacao", r"resultados da",
)
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+")


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def cliches_encontrados(texto: str) -> list[str]:
    """Ex.: cliches_encontrados("Apresento com otimismo…") -> ["otimis", "apresento"]"""
    normalizado = _normalizar(texto)
    achados = [padrao for padrao in PADROES_CLICHE if re.search(padrao, normalizado)]
    return achados + (["emoji"] if EMOJI.search(texto) else [])


def remover_frases_com_cliche(texto: str) -> str:
    frases = FIM_DE_FRASE.split(EMOJI.sub("", texto).strip())
    return " ".join(f for f in frases if f and not cliches_encontrados(f)).strip()


def formatar_reais(valor: float) -> str:
    """Ex.: formatar_reais(1668.337) -> "R$ 1.668,34" """
    return "R$ " + f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _pct(valor: float) -> str:
    return f"{valor:.0f}%" if abs(valor) >= 10 else f"{valor:.1f}%".replace(".", ",")


def _maior_fatia(quebras: list[dict], nomes: dict[str, str], total: float) -> tuple[str, str] | None:
    afetadas = [q for q in quebras if q["diferenca"]]
    if not afetadas or not total:
        return None
    maior = max(afetadas, key=lambda q: q["diferenca"])
    return nomes.get(maior["codigo"], maior["codigo"]), _pct(maior["diferenca"] / total * 100)


def fatos_da_simulacao(resumo: dict) -> list[str]:
    """Os números da simulação como frases curtas em português, prontas para a LLM usar."""
    totais = resumo["totais"]
    custo = totais["diferenca"]
    fatos = [
        f"Custo extra da campanha: {formatar_reais(custo)} ({_pct(totais['diferenca_pct'])} sobre a comissão atual de {formatar_reais(totais['baseline'])}).",
        _fato_orcamento(resumo["orcamento"]),
        _fato_meta(resumo["meta"]),
        *_fatos_impacto(resumo.get("impacto"), resumo.get("maiores_lojas", []), custo),
    ]
    marca = _maior_fatia(resumo["por_marca"], NOMES_MARCA, custo)
    cargo = _maior_fatia(resumo["por_cargo"], NOMES_CARGO, custo)
    if marca:
        fatos.append(f"Maior parte do custo extra: marca {marca[0]} ({marca[1]} do total).")
    if cargo:
        fatos.append(f"Cargo que mais recebe o acréscimo: {cargo[0]} ({cargo[1]} do total).")
    return fatos + [_fato_cenario(cenario) for cenario in resumo.get("cenarios", [])]


def _fato_meta(meta: dict) -> str:
    """Histórico, não previsão: evita "meta batida" e "superou em 120%" (é 120% DA meta)."""
    pct = meta["pct_atingimento"]
    comparacao = f"{_pct(pct - 100)} acima da meta" if pct >= 100 else f"{_pct(100 - pct)} abaixo da meta"
    return (
        f"No histórico, as vendas desse período somaram {formatar_reais(meta['vendas_periodo'])}, "
        f"{_pct(pct)} da meta de {formatar_reais(meta['meta_vendas'])} ({comparacao})."
    )


def _fatos_impacto(impacto: dict | None, lojas: list[dict], custo: float) -> list[str]:
    if not impacto or not impacto["pessoas_impactadas"]:
        return []
    fatos = [
        f"{impacto['pessoas_impactadas']} de {impacto['pessoas_total']} pessoas recebem o acréscimo, "
        f"em média {formatar_reais(impacto['media_por_pessoa'])} cada (maior: {formatar_reais(impacto['maior_acrescimo'])})."
    ]
    if lojas and custo:
        maior = lojas[0]
        fatos.append(f"Loja com maior custo extra: loja {maior['codigo']}, {formatar_reais(maior['diferenca'])} ({_pct(maior['diferenca'] / custo * 100)} do total).")
    return fatos


def _fato_cenario(cenario: dict) -> str:
    situacao = "cabe no orçamento" if cenario["cabe_no_orcamento"] else "ainda não cabe no orçamento"
    pct = f"{cenario['pct_acrescimo']:.2f}".replace(".", ",")
    return (
        f"Cenário calculado '{cenario['titulo']}': acréscimo de {pct}%, custo extra "
        f"{formatar_reais(cenario['custo_incremental'])}, {situacao}."
    )


def _fato_orcamento(orcamento: dict) -> str:
    limite = formatar_reais(orcamento["orcamento_limite"])
    if orcamento["cabe_no_orcamento"]:
        return f"Cabe no orçamento de {limite}; sobram {formatar_reais(orcamento['folga'])}."
    return f"Não cabe no orçamento de {limite}; passa {formatar_reais(-orcamento['folga'])}."


def resumo_deterministico(resumo: dict) -> str:
    """Texto sem LLM, só com os fatos. Ex.: "Custo extra da campanha: R$ 1.668,34 (…)."""
    return " ".join(fatos_da_simulacao(resumo))
