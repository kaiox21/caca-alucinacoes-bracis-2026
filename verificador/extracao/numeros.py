"""Números de processo no texto: CNJ e sequencial, com o ruído de formatação do Nível 2.

Trabalha sobre o texto já normalizado (`verificador.normalizacao`). Nenhum dígito é
inferido, completado ou aproximado (DEC-002). A única leitura que muda um caractere é a
da letra de confusão de OCR colada a dígito (`170076O`, `21737l8`, `1.45g.779`), e ela
vale só aqui, dentro do número: no resto do documento `art. 5o` continua `5o`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# alfabeto de confusão de OCR (harness/02-tarefa/02-niveis-e-ruido.md, contexto numérico)
_OCR = {"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "g": "9", "G": "6", "B": "8"}

_H = r"[ \t]*"  # espaço horizontal
# ninguém começa um número colado a outro: "2022.3657393" não vira "3657393"
_INICIO = r"(?<!\d)(?<!\d[.\-])"
_SEP_HIFEN = rf"{_H}-{{1,2}}{_H}\n?{_H}"  # "-", "- ", "--⏎"
_SEP_BLOCO = rf"{_H}(?:[.\-]{_H})?\n?{_H}(?:[.\-]{_H})?"  # ".", ". ", " ", "", "-⏎.", ".⏎"
_CNJ = re.compile(
    rf"{_INICIO}\d{{1,7}}{_SEP_HIFEN}\d{{2}}{_SEP_BLOCO}\d{{4}}{_SEP_BLOCO}\d{_SEP_BLOCO}\d{{2}}{_SEP_BLOCO}\d{{4}}(?!\d)"
)
# sequencial com milhar: ".", ". ", ".-⏎", "-⏎."; depois do primeiro grupo, só grupos de 3 dígitos
_SEP_MILHAR = rf"(?:{_H}\.{_H}-?{_H}\n?{_H}|{_H}-{_H}\n{_H}\.?{_H})"
_PONTUADO = re.compile(rf"{_INICIO}\d+(?:{_SEP_MILHAR}\d{{3}}(?!\d))*")
# espaço como separador só quando todos os grupos seguintes têm 3 dígitos: "1 821 663", "66 152"
_ESPACADO = re.compile(rf"{_INICIO}\d{{1,3}}(?:[ \t]+\d{{3}}(?!\d))+")


@dataclass(frozen=True)
class Numero:
    inicio: int
    fim: int
    digitos: str  # só a sequência de dígitos, sem separadores e sem zero acrescentado


def ler_digitos_de_ocr(texto: str) -> str:
    """Mesmo comprimento: letra de confusão colada a dígito vira o dígito."""
    caracteres = list(texto)
    for i, caractere in enumerate(texto):
        if caractere not in _OCR:
            continue
        antes = texto[i - 1] if i else ""
        depois = texto[i + 1] if i + 1 < len(texto) else ""
        # "170076O (SP)", "1.45g.779", "4S5"; nunca "2os" nem "12345SP"
        if (antes.isdigit() and (depois.isdigit() or not depois.isalpha())) or (
            depois.isdigit() and (antes.isdigit() or antes == ".")
        ):
            caracteres[i] = _OCR[caractere]
    return "".join(caracteres)


def achar_numeros(texto: str, minimo_de_digitos: int = 2) -> list[Numero]:
    """Todos os números do texto, sem sobreposição. CNJ tem prioridade, depois o espaçado."""
    lido = ler_digitos_de_ocr(texto)
    ocupados: list[tuple[int, int]] = []
    numeros = []
    for padrao in (_CNJ, _ESPACADO, _PONTUADO):
        for m in padrao.finditer(lido):
            if any(m.start() < fim and inicio < m.end() for inicio, fim in ocupados):
                continue
            digitos = re.sub(r"\D", "", m.group())
            if len(digitos) < minimo_de_digitos:
                continue
            ocupados.append(m.span())
            numeros.append(Numero(m.start(), m.end(), digitos))
    return sorted(numeros, key=lambda n: n.inicio)
