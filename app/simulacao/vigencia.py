"""A6-74: composição determinística de percentuais, períodos e conflitos.

Percentuais são literais (0.5 = meio ponto percentual). Datas são inclusivas.
Pendentes participam apenas dos conflitos. A última substituição aprovada vence;
os acréscimos aprovados somam sobre ela, conforme a regra provisória A6-73.
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
    model_config = ConfigDict(allow_inf_nan=False)

    id: str
    nome: str
    tipo: Literal['ACRESCIMO', 'SUBSTITUICAO']
    status: Literal['APROVADA', 'AGUARDANDO_APROVACAO']
    data_inicio: date
    data_fim: date
    marcas_alvo: list[str] = Field(min_length=1)
    cargos_alvo: list[str] = Field(min_length=1)
    percentual: Decimal | None = Field(default=None, ge=0)
    marca_referencia: str | None = None
    autor: str | None = None
    aprovador: str | None = None
    aprovada_em: datetime | None = None
    justificativa: str | None = None
    origem: str = 'CAMPANHA'

    @model_validator(mode='after')
    def validar(self):
        if self.data_inicio > self.data_fim:
            raise ValueError('Campanha com data_inicio posterior à data_fim')
        if self.tipo == 'ACRESCIMO' and (self.percentual is None or self.marca_referencia is not None):
            raise ValueError('ACRESCIMO exige percentual e não admite marca_referencia')
        if self.tipo == 'SUBSTITUICAO' and ((self.percentual is None) == (self.marca_referencia is None)):
            raise ValueError('SUBSTITUICAO exige percentual ou marca_referencia, exclusivamente')
        if self.status == 'APROVADA' and self.origem != 'ESPECIFICACAO' and self.aprovada_em is None:
            raise ValueError('Campanha aprovada exige aprovada_em para ordenar substituições')
        if self.aprovada_em is not None and self.aprovada_em.tzinfo is None:
            raise ValueError('aprovada_em deve conter fuso horário')
        return self


class HistoricoComissao(BaseModel):
    id: str
    nome: str
    tipo: str
    inicio: date
    fim: date
    percentual: float
    acrescimo: float | None = None
    aplicada: bool
    autor: str | None
    aprovador: str | None
    aprovadoEm: datetime | None
    justificativa: str | None
    origem: str


class ComissaoPeriodo(BaseModel):
    id: str
    marca: str
    cargo: str
    inicio: date
    fim: date
    base: float
    vigente: float
    comCampanha: float
    historico: list[HistoricoComissao]
    avisos: list[str]


class ConflitoCampanha(BaseModel):
    id: str
    nome: str
    tipo: str
    status: str
    inicio: date
    fim: date
    marca: str
    cargos: list[str]
    origem: str


def validar_contexto(campanhas: list[CampanhaContexto]) -> None:
    ids = [c.id for c in campanhas]
    if len(set(ids)) != len(ids):
        raise BaselineError('Contexto com campanhas duplicadas; cada versão deve aparecer uma única vez')


def _taxas(comissoes: pd.DataFrame) -> dict[tuple[str, str], Decimal]:
    taxas = {}
    for linha in comissoes.itertuples(index=False):
        chave = (str(linha.cod_marca), str(linha.cod_cargo))
        valor = Decimal(str(linha.pct_comiss))
        if chave in taxas or not valor.is_finite() or valor < 0:
            raise BaselineError(f'Percentual base inválido ou duplicado para {chave}')
        taxas[chave] = valor
    return taxas


def _percentual(campanha: CampanhaContexto, cargo: str, taxas: dict) -> Decimal:
    if campanha.marca_referencia is None:
        return campanha.percentual
    chave = (campanha.marca_referencia, cargo)
    if chave not in taxas:
        raise BaselineError(f'Sem percentual da marca/cargo de referência {chave} para {campanha.id}')
    return taxas[chave]


def _cobre(campanha: CampanhaContexto, marca: str, cargo: str, dia: date) -> bool:
    return (campanha.data_inicio <= dia <= campanha.data_fim
            and marca in campanha.marcas_alvo and cargo in campanha.cargos_alvo)


def _ordem(campanha: CampanhaContexto):
    # Empate de timestamp é resolvido pelo id estável e explicitado no aviso.
    return (campanha.aprovada_em or datetime.min.replace(tzinfo=timezone.utc), campanha.id)


def _vigente(base: Decimal, cargo: str, ativas: list[CampanhaContexto], taxas: dict):
    substituicoes = sorted((c for c in ativas if c.tipo == 'SUBSTITUICAO'), key=_ordem)
    ultima = substituicoes[-1] if substituicoes else None
    percentual = _percentual(ultima, cargo, taxas) if ultima else base
    percentual += sum((_percentual(c, cargo, taxas) for c in ativas if c.tipo == 'ACRESCIMO'), Decimal(0))
    return percentual, ultima


def calcular_periodos(parametros: ParametrosSimulacao, comissoes: pd.DataFrame,
                      campanhas: list[CampanhaContexto]) -> list[ComissaoPeriodo]:
    validar_contexto(campanhas)
    taxas = _taxas(comissoes)
    resultado = []
    for marca in sorted(set(parametros.marcas_alvo)):
        for cargo in sorted(set(parametros.cargos_alvo)):
            if (marca, cargo) not in taxas:
                raise BaselineError(f'Sem % base para marca/cargo {(marca, cargo)}')
            aprovadas = [c for c in campanhas if c.status == 'APROVADA'
                         and marca in c.marcas_alvo and cargo in c.cargos_alvo
                         and c.data_inicio <= parametros.data_fim and c.data_fim >= parametros.data_inicio]
            limites = {parametros.data_inicio}
            for c in aprovadas:
                limites.add(max(c.data_inicio, parametros.data_inicio))
                if c.data_fim < parametros.data_fim:
                    limites.add(c.data_fim + timedelta(days=1))
            limites = sorted(limites)
            for i, inicio in enumerate(limites):
                fim = limites[i + 1] - timedelta(days=1) if i + 1 < len(limites) else parametros.data_fim
                ativas = sorted([c for c in aprovadas if _cobre(c, marca, cargo, inicio)], key=_ordem)
                base = taxas[marca, cargo]
                vigente, ultima = _vigente(base, cargo, ativas, taxas)
                avisos = []
                if len(ativas) > 1:
                    avisos.append('Sobreposição: acréscimos aprovados são somados (regra provisória A6-73).')
                if sum(c.tipo == 'SUBSTITUICAO' for c in ativas) > 1:
                    avisos.append('Mais de uma substituição: vale a aprovada por último; empate de data usa o id.')
                historico = [HistoricoComissao(
                    id=c.id, nome=c.nome, tipo=c.tipo, inicio=c.data_inicio, fim=c.data_fim,
                    percentual=float(_percentual(c, cargo, taxas)),
                    acrescimo=float(c.percentual) if c.tipo == 'ACRESCIMO' else None,
                    aplicada=c.tipo == 'ACRESCIMO' or c is ultima,
                    autor=c.autor, aprovador=c.aprovador, aprovadoEm=c.aprovada_em,
                    justificativa=c.justificativa, origem=c.origem,
                ) for c in ativas]
                resultado.append(ComissaoPeriodo(
                    id=f'{marca}:{cargo}:{inicio}:{fim}', marca=marca, cargo=cargo, inicio=inicio, fim=fim,
                    base=float(base), vigente=float(vigente),
                    comCampanha=float(vigente + Decimal(str(parametros.pct_acrescimo))),
                    historico=historico, avisos=avisos,
                ))
    return resultado


def detectar_conflitos(parametros: ParametrosSimulacao,
                      campanhas: list[CampanhaContexto]) -> list[ConflitoCampanha]:
    validar_contexto(campanhas)
    conflitos = []
    for c in sorted(campanhas, key=lambda c: (c.data_inicio, c.id)):
        inicio, fim = max(c.data_inicio, parametros.data_inicio), min(c.data_fim, parametros.data_fim)
        cargos = sorted(set(c.cargos_alvo) & set(parametros.cargos_alvo))
        if inicio > fim or not cargos:
            continue
        for marca in sorted(set(c.marcas_alvo) & set(parametros.marcas_alvo)):
            conflitos.append(ConflitoCampanha(id=c.id, nome=c.nome, tipo=c.tipo, status=c.status,
                inicio=inicio, fim=fim, marca=marca, cargos=cargos, origem=c.origem))
    return conflitos


def calcular_baseline_vigente(bases: BasesSimulacao, campanhas: list[CampanhaContexto]) -> pd.DataFrame:
    """Comissão mensal com as aprovadas, usando a data real de cada venda.

    Mantém a granularidade matrícula/competência do executor. Gerente recebe sobre
    todas as vendas de sua loja; pendentes nunca entram no custo. O pct_comiss da
    tabela continua sendo o base; o detalhamento efetivo está em comissoes_periodo.
    """
    validar_contexto(campanhas)
    baseline = calcular_baseline(bases)
    aprovadas = [c for c in campanhas if c.status == 'APROVADA']
    if not aprovadas:
        return baseline
    taxas = _taxas(bases.comissoes)
    for indice, linha in baseline.iterrows():
        marca, cargo = str(linha.cod_marca), str(linha.cod_cargo)
        relevantes = [c for c in aprovadas if marca in c.marcas_alvo and cargo in c.cargos_alvo]
        if not relevantes:
            continue
        coluna, codigo = ('cod_loja', linha.cod_loja) if cargo == '150' else ('matricula', linha.matricula)
        vendas = bases.vendas[(bases.vendas.competencia == linha.competencia) & (bases.vendas[coluna] == codigo)]
        total = Decimal(0)
        for venda in vendas.itertuples(index=False):
            dia = pd.Timestamp(venda.data_venda).date()
            ativas = [c for c in relevantes if _cobre(c, marca, cargo, dia)]
            vigente, _ = _vigente(taxas[marca, cargo], cargo, ativas, taxas)
            total += Decimal(str(venda.vlr_venda)) * vigente / 100
        baseline.at[indice, 'comissao'] = float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN))
    return baseline
