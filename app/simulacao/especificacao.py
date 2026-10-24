"""Campanhas da especificação Dom Rock: contam como aprovadas na % vigente (estudo A6-73).

O backend manda só as campanhas do sistema (contrato 4.3); estas a Lana carrega sozinha.
Ficam num arquivo até o A6-77 criar a tabela: aí muda só a implementação do catálogo.
"""
import json
from pathlib import Path
from typing import Protocol

from app.simulacao.vigencia import CampanhaContexto

ARQUIVO_2025 = Path(__file__).with_name("especificacao_2025.json")


class CatalogoEspecificacao(Protocol):
    def campanhas(self) -> list[CampanhaContexto]: ...


class ArquivoEspecificacao:
    """Itens 2h, 3g, 4g, 5f, 5g, 6f e 6g do `Especificacao.pdf`. Ex.: ArquivoEspecificacao().campanhas()"""

    def __init__(self, caminho: Path = ARQUIVO_2025) -> None:
        itens = json.loads(caminho.read_text(encoding="utf-8"))
        self._campanhas = [CampanhaContexto.model_validate(item) for item in itens]

    def campanhas(self) -> list[CampanhaContexto]:
        return list(self._campanhas)
