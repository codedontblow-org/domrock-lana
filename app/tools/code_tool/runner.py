"""Execução isolada do código gerado.

Sprint 1: subprocesso `python -I` com ambiente vazio, timeout e `setrlimit` (memória, CPU,
escrita em disco). Limitação aceita: roda no mesmo container da Lana. A Sprint 2 pode trocar
por um container efêmero sem rede, implementando o mesmo protocolo `CodeRunner`.
"""
import json
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Protocol

import pandas as pd

CAMINHO_HARNESS = Path(__file__).with_name("harness.py")
LIMITE_MEMORIA_BYTES = 2 * 1024**3
TIMEOUT_PADRAO_S = 60
MARGEM_CPU_S = 5


@dataclass(frozen=True)
class ExecucaoCodigo:
    """Resultado de uma execução: `status` é ok, erro_codigo, timeout ou erro_harness."""

    status: str
    apuracao_simulada: pd.DataFrame | None = None
    contribuicoes: pd.DataFrame | None = None
    mensagem: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class CodeRunner(Protocol):
    def executar(
        self, fonte: str, bases: dict[str, pd.DataFrame], apuracao_base: pd.DataFrame,
        competencias: list[str],
    ) -> ExecucaoCodigo: ...


class SubprocessRunner:
    """Ex.: SubprocessRunner(timeout_s=30).executar(fonte, bases, baseline, ["2025-10"])"""

    def __init__(self, timeout_s: int = TIMEOUT_PADRAO_S) -> None:
        self._timeout_s = timeout_s

    def executar(
        self, fonte: str, bases: dict[str, pd.DataFrame], apuracao_base: pd.DataFrame,
        competencias: list[str],
    ) -> ExecucaoCodigo:
        payload = _montar_payload(fonte, bases, apuracao_base, competencias)
        try:
            processo = self._rodar(payload)
        except subprocess.TimeoutExpired:
            return ExecucaoCodigo("timeout", mensagem=f"Execução passou de {self._timeout_s}s")
        return _ler_envelope(processo)

    def _rodar(self, payload: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as diretorio_vazio:
            return subprocess.run(
                [sys.executable, "-I", "-B", str(CAMINHO_HARNESS)],
                input=payload, capture_output=True, text=True, timeout=self._timeout_s,
                env={}, cwd=diretorio_vazio, preexec_fn=self._limitar_recursos,
            )

    def _limitar_recursos(self) -> None:
        resource.setrlimit(resource.RLIMIT_AS, (LIMITE_MEMORIA_BYTES, LIMITE_MEMORIA_BYTES))
        # Rede de segurança acima do timeout de relógio, para o timeout ser reportado como tal.
        limite_cpu = self._timeout_s + MARGEM_CPU_S
        resource.setrlimit(resource.RLIMIT_CPU, (limite_cpu, limite_cpu))
        # Bloqueia escrita em arquivos regulares; stdout/stdin são pipes e não são afetados.
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))


def _montar_payload(
    fonte: str, bases: dict[str, pd.DataFrame], apuracao_base: pd.DataFrame, competencias: list[str],
) -> str:
    return json.dumps({
        "fonte": fonte,
        "competencias": competencias,
        "bases": {nome: _para_json(tabela) for nome, tabela in bases.items()},
        "apuracao_base": _para_json(apuracao_base),
    })


def _para_json(tabela: pd.DataFrame) -> str:
    return tabela.to_json(orient="records", date_format="iso")


def _ler_envelope(processo: subprocess.CompletedProcess[str]) -> ExecucaoCodigo:
    try:
        envelope = json.loads(processo.stdout)
    except json.JSONDecodeError:
        return ExecucaoCodigo(
            "erro_harness",
            mensagem=f"Saída inválida (exit {processo.returncode}): {processo.stderr[-1000:]}",
        )
    if envelope["status"] != "ok":
        return ExecucaoCodigo(envelope["status"], mensagem=f"{envelope['mensagem']}\n{envelope['traceback']}")
    return ExecucaoCodigo(
        "ok",
        apuracao_simulada=_de_json(envelope["apuracao_simulada"]),
        contribuicoes=_de_json(envelope["contribuicoes"]),
    )


def _de_json(registros_json: str) -> pd.DataFrame:
    return pd.read_json(StringIO(registros_json), orient="records", dtype=False)
