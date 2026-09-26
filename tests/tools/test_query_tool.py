"""Regressão: o commit 547fbf3 apagou o corpo de `consultar_banco`, que passou a
retornar None e deixou o agente sem acesso ao banco."""
import sys
import types

from app.tools.query_tool.dtos import QueryRequestBody, QueryResponseBody


class FakeQueryService(types.ModuleType):
    """Substitui `query_tool.service`, que chama a LLM e o Postgres ao ser importado."""

    def __init__(self) -> None:
        super().__init__("app.tools.query_tool.service")
        self.perguntas_recebidas: list[str] = []

    def executar(self, body: QueryRequestBody) -> QueryResponseBody:
        self.perguntas_recebidas.append(body.pergunta)
        return QueryResponseBody(status="sucesso", sql_gerado="SELECT 1", dados=[{"total": 1}])


def test_consultar_banco_repassa_pergunta_e_devolve_resposta(monkeypatch) -> None:
    fake_service = FakeQueryService()
    monkeypatch.setitem(sys.modules, "app.tools.query_tool.service", fake_service)
    monkeypatch.delitem(sys.modules, "app.tools.query_tool.tool", raising=False)
    from app.tools.query_tool.tool import consultar_banco

    resposta = consultar_banco.invoke({"pergunta": "Quantas vendas em outubro?"})

    assert fake_service.perguntas_recebidas == ["Quantas vendas em outubro?"]
    assert resposta["status"] == "sucesso"
    assert resposta["dados"] == [{"total": 1}]
