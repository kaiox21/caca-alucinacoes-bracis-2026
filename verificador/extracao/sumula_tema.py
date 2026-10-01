"""Súmula e tema, com a palavra-chave tolerante a ruído de OCR (`5úmula`, `Temã`).

A palavra-chave só vale seguida de número, e o tema exige `da repercussão geral` ou
`repetitivo`: é o que impede `tema` e `súmula` em texto corrido de virarem citação.
"""
from __future__ import annotations

import re

from .achado import Achado
from .tolerancia import tolerante

_TRIBUNAL = r"STF|STJ|STM|TSE|TST"
_POR_EXTENSO = {
    "Supremo Tribunal Federal": "STF", "Superior Tribunal de Justiça": "STJ", "Superior Tribunal Militar": "STM",
    "Tribunal Superior Eleitoral": "TSE", "Tribunal Superior do Trabalho": "TST",
}
_TRIBUNAL_POR_EXTENSO = "|".join(
    rf"(?P<ext{sigla}>" + r"\s+".join(tolerante(palavra) for palavra in nome.split()) + ")"
    for nome, sigla in _POR_EXTENSO.items()
)
# o tribunal por extenso e o item ("Súmula 331, IV, do TST") só entram no span com o tribunal depois:
# sem ele, "Súmula 83 do Supremo Tribunal Federal" resolveria pela Súmula 83 de outro tribunal
_SUMULA = re.compile(
    rf"(?<![\w])(?:{tolerante('Súmula')}(?![A-Za-zÀ-ÿ])|{tolerante('Súm')}\.)\s+"
    rf"(?P<vinc>{tolerante('Vinculante')}\s+)?(?:n\.?[º°o.]?\.?\s*)?(?P<num>\d{{1,4}})(?!\d)"
    rf"(?:(?:,\s*(?:item\s+|inciso\s+)?[IVXLC]+(?![A-Za-z]))?"
    rf"(?:,?\s+d[oa]\s+(?:(?P<trib>{_TRIBUNAL})(?![A-Za-z])|{_TRIBUNAL_POR_EXTENSO})"
    rf"|\s*/\s*(?P<trib2>{_TRIBUNAL})(?![A-Za-z])))?"
)
_TEMA = re.compile(
    rf"(?<![\w]){tolerante('Tema')}\s+(?:n\.?[º°o.]?\.?\s*)?(?P<num>\d[\d.]*\d|\d)\s+"
    rf"(?:da\s+{tolerante('repercussão')}\s+{tolerante('geral')}|d[oa]s?\s+(?:{tolerante('recursos')}\s+)?{tolerante('repetitivos')}?)"
)


def extrair_sumulas(texto: str) -> list[Achado]:
    achados = []
    for m in _SUMULA.finditer(texto):
        vinculante = bool(m.group("vinc"))
        por_extenso = next((sigla for sigla in _POR_EXTENSO.values() if m.group(f"ext{sigla}")), None)
        tribunal = m.group("trib") or m.group("trib2") or por_extenso or ("STF" if vinculante else None)
        achados.append(Achado(m.start(), m.end(), "sumula", m.span("num"), numero=m.group("num"),
                              tribunal=tribunal, vinculante=vinculante))
    return achados


def extrair_temas(texto: str) -> list[Achado]:
    return [Achado(m.start(), m.end(), "tema", m.span("num"), numero=m.group("num").replace(".", ""))
            for m in _TEMA.finditer(texto)]
