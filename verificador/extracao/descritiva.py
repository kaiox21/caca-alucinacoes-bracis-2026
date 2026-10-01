"""Referência descritiva: tribunal ou classe + ano + relator, sem número de processo.

A âncora é o miolo `[do TRIB] [proferido|julgado] em|de ANO, <relatoria> NOME`, e o
cabeçalho fica à esquerda dele: uma das palavras do molde (`julgado`, `precedente`,
`acórdão`), que exige o tribunal, ou uma classe processual achada pelo mesmo vocabulário
de cadeias que o processo usa, por sigla ou por extenso. A classe não é uma lista tirada do
gabarito: uma descritiva perdida é falso negativo de `incompleta`, o erro mais caro por
citação. Conectivos e nome do relator toleram ruído de letra e quebra de linha (DEC-012).
"""
from __future__ import annotations

import re

from .achado import Achado
from .numeros import ler_digitos_de_ocr
from .processo import inicio_da_cadeia
from .tolerancia import tolerante

_TRIBUNAL = r"STF|STJ|STM|TSE|TST"
_PALAVRA_DO_NOME = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ'’-]*"
# o nome pode quebrar de linha uma vez entre duas palavras, nunca atravessar uma linha em branco:
# depois de "…relatoria de Rosa Weber" e um parágrafo novo, "II" não é sobrenome
_ESPACO_DO_NOME = r"(?:[ \t]+|[ \t]*\n[ \t]*)"
_NOME = rf"{_PALAVRA_DO_NOME}(?:{_ESPACO_DO_NOME}(?:(?:d[aeo]s?|e){_ESPACO_DO_NOME})?{_PALAVRA_DO_NOME})*"
# a coluna `relator` da base às vezes traz o título ("Min. CRISTIANO ZANIN"), e a citação pode copiar
_TITULO = r"(?:(?:[Mm][Ii][Nn]|[Dd][Ee][Ss]|[Dd][Rr][Aa]?)\.\s*)?"
# "pela relatoria de", "da relatoria de", "sob a relatoria de", "relatado por", "Rel. Min."
_RELATORIA = (
    rf"(?:(?:{tolerante('pela')}|{tolerante('da')}|{tolerante('sob')})\s+(?:a\s+)?{tolerante('relatoria')}\s+d\w"
    rf"|{tolerante('relatado')}\s+{tolerante('por')}"
    rf"|{tolerante('Rel')}\.\s*(?:{tolerante('Min')}\.)?)"
)
_MIOLO = re.compile(
    rf"(?:\s+d[oa]\s+(?P<trib>(?i:{_TRIBUNAL}))(?![A-Za-z]))?,?\s+"
    # o particípio antes do ano varia ("proferido", "julgado", "datado", "decidido"): qualquer
    # palavra terminada em -ado/-ido serve, porque o resto do molde (ano e relator) é que identifica
    rf"(?:[A-Za-zÀ-ÿ]{{3,12}}[ai]d[oa]\s+)?(?:em|de)\s+(?P<ano>[12][0-9OolISgGB]{{3}})(?![\wÀ-ÿ]),?\s+"
    rf"{_RELATORIA}\s+{_TITULO}(?P<nome>{_NOME})"
)
# o cabeçalho do molde é decoração: quem identifica é tribunal (ou classe) + ano + relator
# (DEC-014, forma d). A lista cobre as palavras que abrem esses moldes sem abrir para qualquer coisa.
_CABECALHO_DO_MOLDE = re.compile(
    "(?:" + "|".join(tolerante(palavra) for palavra in
                     ("julgado", "precedente", "acórdão", "decisão", "aresto", "julgamento", "entendimento"))
    + r")\s*$"
)


def extrair_descritivas(texto: str) -> list[Achado]:
    """Referências descritivas do texto normalizado; o span termina no nome do relator."""
    achados = []
    for m in _MIOLO.finditer(texto):
        ano = ler_digitos_de_ocr(m.group("ano"))  # "202S", "2O23": letra de OCR no ano
        if not (ano.isdigit() and 1900 <= int(ano) <= 2100):
            continue
        cabecalho = _CABECALHO_DO_MOLDE.search(texto, max(0, m.start() - 20), m.start())
        if cabecalho and m.group("trib"):
            inicio = cabecalho.start()
        else:
            inicio = inicio_da_cadeia(texto, m.start())
            if inicio is None:
                continue
        fim = m.end("nome")
        while fim > inicio and texto[fim - 1] in ".'’-":  # ponto final da frase não é do nome
            fim -= 1
        achados.append(Achado(inicio, fim, "descritiva", m.span("ano"), numero=ano,
                              tribunal=m.group("trib")))
    return achados
