"""Resolução de citações a processo: dos candidatos do índice para `real`, `inventada` ou `incompleta`.

O índice expõe os candidatos de um número e não escolhe entre eles. Aqui mora a
escolha (DEC-019, DEC-020):

- 0 candidatos: `inventada`;
- 1 registro efetivo (duplicatas contam uma vez, pelo canônico): `real`, qualquer que
  seja a cadeia de classe citada. A classe nunca zera candidatos (DEC-010, DEC-011);
- 2 ou mais registros efetivos: `real` só se a cadeia normalizada da citação for
  **igual** à de exatamente um deles; senão `incompleta`.

A consulta é sempre sem filtro de tribunal (DEC-018). UF, ano e relator não entram no
desempate: na base publicada não separam nenhum grupo que a cadeia já não separe.

A cadeia chega **separada do número**: é o trecho da citação antes do início do número.
Quem separa é o chamador, porque a cadeia pode começar por algarismo (`2ºs Embargos`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .cadeias import normalizar_cadeia
from .indice import Candidato, Indice

Classe = Literal["real", "inventada", "incompleta"]
Motivo = Literal[
    "sem_candidato",
    "candidato_unico",
    "candidato_unico_cadeia_divergente",
    "duplicata",
    "desempate_por_cadeia",
    "sem_desempate",
]

# confiança fixa por regra, no valor que a evidência sustenta (DEC-016, emendada; EXP-006).
# O bônus da métrica é máximo quando a confiança é a probabilidade de acerto: as regras que o
# mundo fechado decide valem 1,0; as duas que o harness registra como aposta mantêm a ressalva.
CONFIANCAS: dict[Motivo, float] = {
    "candidato_unico": 1.0,
    "duplicata": 1.0,
    "desempate_por_cadeia": 1.0,
    "sem_candidato": 1.0,
    # com um único registro efetivo a classe citada não muda a contagem (DEC-010), e a
    # cardinalidade oficial decide: 1 candidato é `real`, divergindo a classe ou não
    "candidato_unico_cadeia_divergente": 1.0,
    "sem_desempate": 0.50,  # a única que declara não saber (DEC-020)
}

_TRIBUNAIS = {"TST", "STJ", "STF", "TSE", "STM"}
# "Processo nº TST-RR-...": o gabarito põe o prefixo dentro do span
_PREFIXO_PROCESSO = re.compile(r"^\s*processo\s+(?:n[º°o.]{0,2}\s+)?", re.IGNORECASE)
# "nº", "n°", "n.", "n.º", "No" logo antes do número
_MARCADOR_DE_NUMERO = re.compile(r"\bn\.?[º°o]?\.?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Resolucao:
    classe: Classe
    id_canonico: int | None
    confianca: float
    motivo: Motivo
    candidatos: tuple[Candidato, ...] = ()


def normalizar_cadeia_citada(cadeia_citada: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Tokens e resíduo da cadeia como escrita na citação, sem o que não é classe."""
    texto = _PREFIXO_PROCESSO.sub("", cadeia_citada or "")
    texto = _MARCADOR_DE_NUMERO.sub("", texto.strip())
    tokens, residuo = normalizar_cadeia(texto)
    return tokens, tuple(palavra for palavra in residuo if palavra not in _TRIBUNAIS)


def _resolucao(classe: Classe, motivo: Motivo, candidatos: list[Candidato], escolhido: Candidato | None = None) -> Resolucao:
    return Resolucao(
        classe=classe,
        id_canonico=escolhido.id if escolhido else None,
        confianca=CONFIANCAS[motivo],
        motivo=motivo,
        candidatos=tuple(candidatos),
    )


def _cadeia_confiavel(candidato: Candidato) -> bool:
    tokens, residuo = normalizar_cadeia(candidato.cadeia)
    return bool(tokens) and not residuo


def resolver_processo(indice: Indice, identificador: str, cadeia_citada: str = "") -> Resolucao:
    """Decide a classe de uma citação a processo. Consulta exata, sem filtro de tribunal."""
    candidatos = indice.consultar_processo(identificador)
    if not candidatos:
        return _resolucao("inventada", "sem_candidato", candidatos)

    efetivos = [c for c in candidatos if not c.duplicata or c.canonico]
    tokens, residuo = normalizar_cadeia_citada(cadeia_citada)

    if len(efetivos) == 1:
        (unico,) = efetivos
        if len(candidatos) > 1:
            motivo: Motivo = "duplicata"
        elif tokens and unico.cadeia_normalizada and tokens[-1] != unico.cadeia_normalizada[-1]:
            # classe de base diferente; omitir o recurso interno não conta como divergência
            motivo = "candidato_unico_cadeia_divergente"
        else:
            motivo = "candidato_unico"
        return _resolucao("real", motivo, candidatos, unico)

    # fases recursais distintas: só a igualdade exata da cadeia desempata
    if tokens and not residuo:
        casam = [c for c in efetivos if c.cadeia_normalizada == tokens and _cadeia_confiavel(c)]
        if len(casam) == 1:
            return _resolucao("real", "desempate_por_cadeia", candidatos, casam[0])
    return _resolucao("incompleta", "sem_desempate", candidatos)
