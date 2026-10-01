"""O que cada família de extração devolve: um span e os identificadores já separados."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Familia = Literal["processo", "sumula", "tema", "lei", "descritiva"]


@dataclass(frozen=True)
class Achado:
    inicio: int
    fim: int
    familia: Familia
    ancora: tuple[int, int]  # onde está o identificador (número, artigo, ano): sempre dentro do span
    numero: str = ""  # processo: só dígitos; súmula e tema: o número; lei: o artigo
    cadeia: str = ""  # processo: o trecho do span antes do número
    diploma: str = ""  # lei
    tribunal: str | None = None  # súmula
    vinculante: bool = False  # súmula
    # cadeia achada só no passo relaxado (em minúscula): delimita o span, mas não desempata
    cadeia_confiavel: bool = True

    @property
    def tamanho(self) -> int:
        return self.fim - self.inicio
