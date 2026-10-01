"""Normalização e validação das chaves numéricas de processo.

A chave é só a sequência de dígitos do número (DEC-010, emendada: o tribunal é
atributo do candidato, não parte da chave). Um número no padrão CNJ vira 20
dígitos, com zeros à esquerda; um número sequencial fica sem zeros à esquerda.
A mesma função serve ao registro da base e ao identificador consultado, e não
há casamento aproximado em lugar nenhum.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Segmento de justiça (o "J" do CNJ) esperado para os tribunais da base que usam CNJ.
SEGMENTO_POR_TRIBUNAL = {"TST": "5", "TSE": "6", "STM": "7"}

# Um CNJ tem 20 dígitos; com o sequencial sem zeros à esquerda, no mínimo 14.
_MIN_DIGITOS_CNJ = 14
_MAX_DIGITOS_CNJ = 20

_NAO_DIGITO = re.compile(r"\D")


def so_digitos(texto: str) -> str:
    return _NAO_DIGITO.sub("", texto)


@dataclass(frozen=True)
class Cnj:
    """Número único de processo: NNNNNNN-DD.AAAA.J.TR.OOOO."""

    sequencial: str  # 7 dígitos
    dv: str  # 2 dígitos
    ano: str  # 4 dígitos
    segmento: str  # 1 dígito
    tribunal: str  # 2 dígitos
    origem: str  # 4 dígitos

    @property
    def chave(self) -> str:
        return self.sequencial + self.dv + self.ano + self.segmento + self.tribunal + self.origem

    def __str__(self) -> str:
        return (
            f"{self.sequencial}-{self.dv}.{self.ano}.{self.segmento}.{self.tribunal}.{self.origem}"
        )


def decompor_cnj(texto: str) -> Cnj | None:
    """Lê os campos da direita para a esquerda, que é onde os tamanhos são fixos.

    O sequencial é o único campo de tamanho variável na escrita (zeros à esquerda
    costumam ser omitidos), então é o que sobra à esquerda.
    """
    d = so_digitos(texto)
    if not _MIN_DIGITOS_CNJ <= len(d) <= _MAX_DIGITOS_CNJ:
        return None
    return Cnj(
        sequencial=d[:-13].zfill(7),
        dv=d[-13:-11],
        ano=d[-11:-7],
        segmento=d[-7],
        tribunal=d[-6:-4],
        origem=d[-4:],
    )


def dv_esperado(cnj: Cnj) -> str:
    """Dígito verificador pelo módulo 97 (Resolução CNJ 65/2008, anexo VIII)."""
    base = int(cnj.sequencial + cnj.ano + cnj.segmento + cnj.tribunal + cnj.origem + "00")
    return f"{98 - base % 97:02d}"


@dataclass(frozen=True)
class Validacao:
    valido: bool
    cnj: Cnj | None
    motivo: str | None  # "estrutura", "segmento" ou "digito_verificador"


def validar_cnj(texto: str, tribunal: str | None = None) -> Validacao:
    """Valida estrutura, segmento de justiça esperado para o tribunal e dígito verificador."""
    cnj = decompor_cnj(texto)
    if cnj is None or not 1900 <= int(cnj.ano) <= 2100 or int(cnj.sequencial) == 0:
        return Validacao(False, cnj, "estrutura")
    esperado = SEGMENTO_POR_TRIBUNAL.get(tribunal or "")
    if esperado is not None and cnj.segmento != esperado:
        return Validacao(False, cnj, "segmento")
    if cnj.dv != dv_esperado(cnj):
        return Validacao(False, cnj, "digito_verificador")
    return Validacao(True, cnj, None)


def chave_numerica(identificador: str) -> str:
    """Chave de consulta: só dígitos; CNJ em 20 dígitos, sequencial sem zeros à esquerda.

    Devolve string vazia quando o identificador não tem dígito nenhum.
    """
    d = so_digitos(identificador)
    if not d:
        return ""
    if len(d) >= _MIN_DIGITOS_CNJ:
        return d.zfill(_MAX_DIGITOS_CNJ)[-_MAX_DIGITOS_CNJ:]
    return d.lstrip("0") or "0"
