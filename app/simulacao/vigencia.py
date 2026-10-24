"""A6-74: composição determinística da % vigente, dos trechos e dos conflitos (contrato 2.3).

Percentuais são literais (0.5 = meio ponto percentual). Datas são inclusivas.
Pendentes participam apenas dos conflitos. A última substituição aprovada vence;
os acréscimos aprovados somam sobre ela (soma com aviso, regra provisória do estudo A6-73).
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.simulacao.baseline import BaselineError, calcular_baseline
from app.simulacao.bases import BasesSimulacao
from app.tools.regra_tool.dtos import ParametrosSimulacao


class CampanhaContexto(BaseModel):
    """Campanha que pode compor a % vigente: uma versão salva no sistema (4.3) ou um item da especificação.

    O item da especificação vem com `campanha_id`, `versao`, `autor`, `aprovador` e `aprovada_em` nulos (2.3).
    """

    model_config = ConfigDict(allow_inf_nan=False)

    campanha_id: int | None = None
    versao: int | None = None
    tipo: Literal['ACRESCIMO', 'SUBSTITUICAO']
    nome: str
    status: Literal['APROVADA', 'AGUARDANDO_APROVACAO']
    autor: str | None = None
    aprovador: str | None = None
    aprovada_em: datetime | None = None
    justificativa: str | None = None
    data_inicio: date
    data_fim: date
    pct_acrescimo: Decimal | None = Field(default=None, ge=0)
    pct_novo: Decimal | None = Field(default=None, ge=0)
    # Só a especificação: a 3g troca a % da marca 10 pela da marca 20 no mesmo cargo.
    marca_referencia: str | None = None
    marcas_alvo: list[str] = Field(min_length=1)
    cargos_alvo: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def validar(self) -> 'CampanhaContexto':
        erro = _erro_de_campanha(self)
        if erro:
            raise ValueError(f'Campanha {self.nome!r}: {erro}')
        return self

    @property
    def chave(self) -> str:
        """A versão da campanha do sistema, ou o nome do item da especificação."""
        return self.nome if self.campanha_id is None else f'{self.campanha_id}-v{self.versao}'


def _erro_de_campanha(c: CampanhaContexto) -> str | None:
    if c.data_inicio > c.data_fim:
        return f'data_inicio {c.data_inicio} depois de data_fim {c.data_fim}'
    if c.tipo == 'ACRESCIMO' and (c.pct_acrescimo is None or c.pct_novo is not None or c.marca_referencia):
        return f'ACRESCIMO exige só pct_acrescimo; recebido pct_novo={c.pct_novo}, marca_referencia={c.marca_referencia}'
    if c.tipo == 'SUBSTITUICAO' and (c.pct_acrescimo is not None or (c.pct_novo is None) == (c.marca_referencia is None)):
        return f'SUBSTITUICAO exige pct_novo ou marca_referencia, um só; recebido pct_novo={c.pct_novo}'
    if c.status == 'APROVADA' and c.campanha_id is not None and c.aprovada_em is None:
        return 'campanha aprovada no sistema exige aprovada_em para ordenar substituições'
    if c.aprovada_em is not None and c.aprovada_em.tzinfo is None:
        return f'aprovada_em sem fuso horário: {c.aprovada_em}'
    return None


class CampanhaDoSistema(CampanhaContexto):
    """Item de `campanhas` no POST /simulacao (contrato 4.3): sempre uma versão salva no backend."""

    campanha_id: int
    versao: int

    @model_validator(mode='after')
    def sem_marca_referencia(self) -> 'CampanhaDoSistema':
        if self.marca_referencia is not None:
            raise ValueError(f'marca_referencia é só da especificação; recebido {self.marca_referencia!r} '
                             f'na campanha {self.campanha_id}')
        return self


class HistoricoComissao(BaseModel):
    """Uma campanha aprovada que leva da % base à vigente no trecho: o "Por quê" do A6-75."""

    campanha_id: int | None
    versao: int | None
    tipo: str
    nome: str
    data_inicio: date
    data_fim: date
    pct_acrescimo: float | None
    pct_novo: float | None
    autor: str | None
    aprovador: str | None
    aprovada_em: datetime | None
    justificativa: str | None


class ComissaoPeriodo(BaseModel):
    """Um trecho de uma marca × cargo da campanha em que a % vigente fica constante."""

    marca: str
    cargo: str
    data_inicio: date
    data_fim: date
    pct_base: float
    pct_vigente: float
    pct_com_campanha: float
    historico: list[HistoricoComissao]


class Sobreposicao(BaseModel):
    data_inicio: date
    data_fim: date


class ConflitoCampanha(BaseModel):
    """Outra campanha com período e ao menos uma marca × cargo em comum; `marcas` e `cargos` são os comuns."""

    campanha_id: int | None
    versao: int | None
    tipo: str
    nome: str
    status: str
    autor: str | None
    data_inicio: date
    data_fim: date
    sobreposicao: Sobreposicao
    marcas: list[str]
    cargos: list[str]


def validar_contexto(campanhas: list[CampanhaContexto]) -> None:
    chaves = [c.chave for c in campanhas]
    duplicadas = sorted({chave for chave in chaves if chaves.count(chave) > 1})
    if duplicadas:
        raise BaselineError(f'Contexto com campanhas duplicadas {duplicadas}; cada versão deve vir uma única vez')


def _taxas(comissoes: pd.DataFrame) -> dict[tuple[str, str], Decimal]:
    taxas = {}
    for linha in comissoes.itertuples(index=False):
        chave = (str(linha.cod_marca), str(linha.cod_cargo))
        valor = Decimal(str(linha.pct_comiss))
        if chave in taxas or not valor.is_finite() or valor < 0:
            raise BaselineError(f'Percentual base inválido ou duplicado para {chave}: {valor}')
        taxas[chave] = valor
    return taxas


def _pct_novo(campanha: CampanhaContexto, cargo: str, taxas: dict) -> Decimal:
    if campanha.marca_referencia is None:
        return campanha.pct_novo
    chave = (campanha.marca_referencia, cargo)
    if chave not in taxas:
        raise BaselineError(f'Sem percentual da marca/cargo de referência {chave} para {campanha.nome!r}')
    return taxas[chave]


def _alcanca(campanha: CampanhaContexto, marca: str, cargo: str) -> bool:
    return marca in campanha.marcas_alvo and cargo in campanha.cargos_alvo


def _cobre(campanha: CampanhaContexto, marca: str, cargo: str, dia: date) -> bool:
    return campanha.data_inicio <= dia <= campanha.data_fim and _alcanca(campanha, marca, cargo)


def _ordem(campanha: CampanhaContexto) -> tuple[datetime, str]:
    # A especificação (sem aprovada_em) vem antes; empate de horário cai na chave estável.
    return (campanha.aprovada_em or datetime.min.replace(tzinfo=timezone.utc), campanha.chave)


def _compor(base: Decimal, cargo: str, ativas: list[CampanhaContexto],
            taxas: dict) -> tuple[Decimal, list[CampanhaContexto]]:
    """% vigente do dia e as campanhas aplicadas: a última substituição aprovada e todos os acréscimos."""
    substituicoes = sorted((c for c in ativas if c.tipo == 'SUBSTITUICAO'), key=_ordem)
    acrescimos = [c for c in ativas if c.tipo == 'ACRESCIMO']
    do_dia = _pct_novo(substituicoes[-1], cargo, taxas) if substituicoes else base
    vigente = do_dia + sum((c.pct_acrescimo for c in acrescimos), Decimal(0))
    return vigente, sorted(substituicoes[-1:] + acrescimos, key=_ordem)


def _trechos(parametros: ParametrosSimulacao, aprovadas: list[CampanhaContexto]) -> list[tuple[date, date]]:
    """O início e o fim de cada campanha cortam o período em trechos de % constante."""
    inicios = {parametros.data_inicio}
    for c in aprovadas:
        inicios.add(max(c.data_inicio, parametros.data_inicio))
        if c.data_fim < parametros.data_fim:
            inicios.add(c.data_fim + timedelta(days=1))
    ordenados = sorted(inicios)
    fins = [inicio - timedelta(days=1) for inicio in ordenados[1:]] + [parametros.data_fim]
    return list(zip(ordenados, fins))


def _float(valor: Decimal | None) -> float | None:
    return None if valor is None else float(valor)


def _historico(campanha: CampanhaContexto, pct_novo: Decimal | None) -> HistoricoComissao:
    return HistoricoComissao(
        campanha_id=campanha.campanha_id, versao=campanha.versao, tipo=campanha.tipo, nome=campanha.nome,
        data_inicio=campanha.data_inicio, data_fim=campanha.data_fim,
        pct_acrescimo=_float(campanha.pct_acrescimo), pct_novo=_float(pct_novo),
        autor=campanha.autor, aprovador=campanha.aprovador, aprovada_em=campanha.aprovada_em,
        justificativa=campanha.justificativa,
    )


def _periodos_de(parametros: ParametrosSimulacao, marca: str, cargo: str,
                 campanhas: list[CampanhaContexto], taxas: dict) -> list[ComissaoPeriodo]:
    if (marca, cargo) not in taxas:
        raise BaselineError(f'Sem % base para marca/cargo {(marca, cargo)}')
    base = taxas[marca, cargo]
    aprovadas = [c for c in campanhas if c.status == 'APROVADA' and _alcanca(c, marca, cargo)
                 and c.data_inicio <= parametros.data_fim and c.data_fim >= parametros.data_inicio]
    periodos = []
    for inicio, fim in _trechos(parametros, aprovadas):
        vigente, aplicadas = _compor(base, cargo, [c for c in aprovadas if _cobre(c, marca, cargo, inicio)], taxas)
        periodos.append(ComissaoPeriodo(
            marca=marca, cargo=cargo, data_inicio=inicio, data_fim=fim, pct_base=float(base),
            pct_vigente=float(vigente), pct_com_campanha=float(vigente + Decimal(str(parametros.pct_acrescimo))),
            historico=[_historico(c, _pct_novo(c, cargo, taxas) if c.tipo == 'SUBSTITUICAO' else None)
                       for c in aplicadas],
        ))
    return periodos


def calcular_periodos(parametros: ParametrosSimulacao, comissoes: pd.DataFrame,
                      campanhas: list[CampanhaContexto]) -> list[ComissaoPeriodo]:
    """`comissao_periodo` (2.3): um item por marca × cargo da campanha e por trecho."""
    validar_contexto(campanhas)
    taxas = _taxas(comissoes)
    return [periodo for marca in sorted(set(parametros.marcas_alvo)) for cargo in sorted(set(parametros.cargos_alvo))
            for periodo in _periodos_de(parametros, marca, cargo, campanhas, taxas)]


def _conflito(parametros: ParametrosSimulacao, campanha: CampanhaContexto) -> ConflitoCampanha | None:
    inicio, fim = max(campanha.data_inicio, parametros.data_inicio), min(campanha.data_fim, parametros.data_fim)
    marcas = sorted(set(campanha.marcas_alvo) & set(parametros.marcas_alvo))
    cargos = sorted(set(campanha.cargos_alvo) & set(parametros.cargos_alvo))
    if inicio > fim or not marcas or not cargos:
        return None
    return ConflitoCampanha(
        campanha_id=campanha.campanha_id, versao=campanha.versao, tipo=campanha.tipo, nome=campanha.nome,
        status=campanha.status, autor=campanha.autor, data_inicio=campanha.data_inicio, data_fim=campanha.data_fim,
        sobreposicao=Sobreposicao(data_inicio=inicio, data_fim=fim), marcas=marcas, cargos=cargos,
    )


def detectar_conflitos(parametros: ParametrosSimulacao,
                       campanhas: list[CampanhaContexto]) -> list[ConflitoCampanha]:
    """`conflitos` (2.3): aprovadas e pendentes que cruzam o período e uma marca × cargo da campanha."""
    validar_contexto(campanhas)
    conflitos = (_conflito(parametros, c) for c in sorted(campanhas, key=_ordem))
    return [conflito for conflito in conflitos if conflito is not None]


def fontes_da_vigente(campanhas: list[CampanhaContexto], periodos: list[ComissaoPeriodo]) -> list[HistoricoComissao]:
    """`trilha.campanhas` (2.2): cada campanha aplicada em algum trecho, uma vez.

    Na substituição por marca de referência (3g), `pct_novo` vem nulo: varia por cargo e está no histórico.
    """
    aplicadas = {(h.campanha_id, h.versao, h.nome) for periodo in periodos for h in periodo.historico}
    return [_historico(c, c.pct_novo) for c in sorted(campanhas, key=_ordem)
            if (c.campanha_id, c.versao, c.nome) in aplicadas]


def calcular_baseline_vigente(bases: BasesSimulacao, campanhas: list[CampanhaContexto]) -> pd.DataFrame:
    """Comissão mensal com as aprovadas, usando a data real de cada venda.

    Mantém a granularidade matrícula/competência do executor. Gerente recebe sobre
    todas as vendas de sua loja; pendentes nunca entram no custo. O pct_comiss da
    tabela continua sendo o base; o detalhamento efetivo está em comissao_periodo.
    """
    validar_contexto(campanhas)
    baseline = calcular_baseline(bases)
    aprovadas = [c for c in campanhas if c.status == 'APROVADA']
    if not aprovadas:
        return baseline
    taxas = _taxas(bases.comissoes)
    for indice, linha in baseline.iterrows():
        marca, cargo = str(linha.cod_marca), str(linha.cod_cargo)
        relevantes = [c for c in aprovadas if _alcanca(c, marca, cargo)]
        if not relevantes:
            continue
        coluna, codigo = ('cod_loja', linha.cod_loja) if cargo == '150' else ('matricula', linha.matricula)
        vendas = bases.vendas[(bases.vendas.competencia == linha.competencia) & (bases.vendas[coluna] == codigo)]
        total = Decimal(0)
        for venda in vendas.itertuples(index=False):
            dia = pd.Timestamp(venda.data_venda).date()
            vigente, _ = _compor(taxas[marca, cargo], cargo, [c for c in relevantes if _cobre(c, marca, cargo, dia)], taxas)
            total += Decimal(str(venda.vlr_venda)) * vigente / 100
        baseline.at[indice, 'comissao'] = float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN))
    return baseline
