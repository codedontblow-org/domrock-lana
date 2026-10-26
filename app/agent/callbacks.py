import json
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import BaseMessage


class ToolEventsCallbackHandler(BaseCallbackHandler):
    """Callback do LangChain para monitoramento e telemetria de ferramentas.

    Registra cada chamada (on_tool_start / on_tool_end / on_tool_error)
    capturando nome da ferramenta, entrada, tempo decorrido em ms e saída/erro.
    """

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []
        self._start_times: dict[str, float] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_times[str(run_id)] = time.perf_counter()

    def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        inicio = self._start_times.pop(str(run_id), None)
        duracao_ms = int(round((time.perf_counter() - inicio) * 1000)) if inicio else 0
        tool_name = kwargs.get("name") or (output.name if hasattr(output, "name") else "ferramenta")

        conteudo = output
        if hasattr(output, "content"):
            conteudo = output.content
        if isinstance(conteudo, str):
            try:
                conteudo = json.loads(conteudo)
            except Exception:
                pass

        evento = {
            "ferramenta": tool_name,
            "tempo": duracao_ms,
            "situacao": "ok",
            "result": conteudo,
        }
        if isinstance(conteudo, dict):
            if "situacao" in conteudo:
                evento["situacao"] = conteudo["situacao"]
            if "tabelas" in conteudo:
                evento["tabelas"] = conteudo["tabelas"]
            if "competencias" in conteudo:
                evento["competencias"] = conteudo["competencias"]
            if "filtros" in conteudo:
                evento["filtros"] = conteudo["filtros"]
            if "registros" in conteudo:
                evento["registros"] = conteudo["registros"]
            if "sql" in conteudo:
                evento["sql"] = conteudo["sql"]

        self.events.append(evento)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        inicio = self._start_times.pop(str(run_id), None)
        duracao_ms = int(round((time.perf_counter() - inicio) * 1000)) if inicio else 0
        tool_name = kwargs.get("name", "ferramenta")

        self.events.append({
            "ferramenta": tool_name,
            "tempo": duracao_ms,
            "situacao": f"erro: {error}",
            "result": None,
        })
