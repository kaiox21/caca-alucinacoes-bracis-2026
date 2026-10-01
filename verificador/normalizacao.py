"""Normalização do documento de entrada que preserva comprimento e offsets.

Cada caractere vira exatamente um caractere, então a posição `i` do texto
normalizado é a posição `i` do original, e todo span achado aqui vale, em
codepoints, sobre o texto como distribuído (invariante 3). Por isso não há mapa
de offsets.

Só caracteres de superfície mudam: espaços Unicode, o sinal de grau usado como
ordinal, os travessões e o `\r` de um arquivo com fim de linha do Windows (`\r\n` vira
espaço + `\n`, e a quebra continua onde estava). Letra nunca vira dígito aqui, nem dígito vira letra:
aplicada ao documento inteiro, a troca faria `art. 5o da CF` virar artigo 50.
Ler `170076O` como `1700760` é papel da extração do número de processo, que sabe
que está dentro de um número (DEC-002).
"""
from __future__ import annotations

import unicodedata

_TROCAS = {
    "°": "º",  # sinal de grau usado como ordinal: n° -> nº
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-",
    "−": "-",
    "⁄": "/",  # barra de fração, que aparece em cabeçalhos da base (2017⁄0020447-2)
}


def _trocar(caractere: str) -> str:
    if caractere in _TROCAS:
        return _TROCAS[caractere]
    # espaços horizontais Unicode (NBSP, espaço fino, ...); quebra de linha e tabulação ficam
    if caractere != " " and unicodedata.category(caractere) == "Zs":
        return " "
    return caractere


def normalizar(texto: str) -> str:
    """Mesmo comprimento do original; só troca caracteres de superfície."""
    if "\r" in texto:
        texto = texto.replace("\r", " ")
    if texto.isascii():
        return texto
    normalizado = "".join(_trocar(c) if ord(c) > 127 else c for c in texto)
    assert len(normalizado) == len(texto)  # "\r" -> " " também é 1 para 1
    return normalizado
