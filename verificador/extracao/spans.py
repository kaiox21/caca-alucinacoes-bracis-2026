"""Conflitos entre famílias, resolvidos num passo só (DEC-015, invariante 4).

Entre candidatos que se sobrepõem, fica o mais extenso (todo candidato contém o próprio
identificador); em empate de tamanho, a precedência é descritiva, lei, súmula, tema,
processo, porque as quatro primeiras têm palavra-chave própria. Os emitidos têm
interseção vazia entre si, o que é mais forte que IoU < 0,5, a regra que invalida a
submissão inteira.
"""
from __future__ import annotations

from .achado import Achado

_PRECEDENCIA = {"descritiva": 0, "lei": 1, "sumula": 2, "tema": 3, "processo": 4}


def resolver_conflitos(candidatos: list[Achado]) -> list[Achado]:
    escolhidos: list[Achado] = []
    for candidato in sorted(candidatos, key=lambda a: (-a.tamanho, _PRECEDENCIA[a.familia], a.inicio)):
        if all(candidato.fim <= outro.inicio or outro.fim <= candidato.inicio for outro in escolhidos):
            escolhidos.append(candidato)
    return sorted(escolhidos, key=lambda a: a.inicio)
