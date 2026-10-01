"""Ponto de entrada: o texto de um documento vira citações no formato do contrato de saída.

Normaliza (1 para 1), extrai por família, resolve contra o índice e devolve cada citação
com o trecho recortado do **original**. A classe sai assim (DEC-012, DEC-013, DEC-016,
DEC-020; FR-04, FR-12): processo pela resolução; súmula e dispositivo pela consulta ao
índice (1 registro = `real`, nenhum = `inventada`, súmula com 2 ou mais = `incompleta`);
tema = `inventada`, porque a base não tem nenhum; descritiva = `incompleta`, sempre.
Nenhuma consulta sai do índice: mundo fechado, offline e determinístico.

A confiança é fixa por regra e vale o que a evidência sustenta (DEC-016 emendada): 1,0
onde a base decide, e menor nas duas regras que o harness registra como aposta.
"""
from __future__ import annotations

from dataclasses import dataclass

from .extracao import Achado, extrair_citacoes
from .indice import Indice
from .normalizacao import normalizar
from .resolucao import Classe, resolver_processo


@dataclass(frozen=True)
class Citacao:
    inicio: int
    fim: int
    trecho: str
    tipo: str  # "jurisprudencia" ou "lei"
    classificacao: Classe
    id_canonico: int | None
    confianca: float
    familia: str
    motivo: str


def _classificar(achado: Achado, indice: Indice) -> tuple[Classe, int | None, float, str]:
    if achado.familia == "processo":
        # cadeia não confiável (achada só em minúscula) delimita o span, mas não desempata
        cadeia = achado.cadeia if achado.cadeia_confiavel else ""
        resolucao = resolver_processo(indice, achado.numero, cadeia)
        return resolucao.classe, resolucao.id_canonico, resolucao.confianca, resolucao.motivo
    if achado.familia == "descritiva":
        return "incompleta", None, 1.0, "descritiva"
    if achado.familia == "tema":
        return "inventada", None, 1.0, "tema_fora_da_base"
    if achado.familia == "sumula":
        candidatos = indice.consultar_sumula(achado.numero, achado.tribunal, achado.vinculante)
    else:
        candidatos = indice.consultar_dispositivo(achado.diploma, achado.numero)
    if len(candidatos) == 1:
        return "real", candidatos[0].id, 1.0, f"{achado.familia}_na_base"
    if not candidatos:
        return "inventada", None, 1.0, f"{achado.familia}_fora_da_base"
    return "incompleta", None, 0.50, f"{achado.familia}_ambigua"


def verificar_documento(texto: str, indice: Indice) -> list[Citacao]:
    """Citações do documento, sem sobreposição, com offsets em codepoints do texto original."""
    citacoes = []
    for achado in extrair_citacoes(normalizar(texto)):
        classe, id_canonico, confianca, motivo = _classificar(achado, indice)
        citacoes.append(Citacao(
            inicio=achado.inicio,
            fim=achado.fim,
            trecho=texto[achado.inicio:achado.fim],
            tipo="lei" if achado.familia == "lei" else "jurisprudencia",
            classificacao=classe,
            id_canonico=id_canonico,
            confianca=confianca,
            familia=achado.familia,
            motivo=motivo,
        ))
    return citacoes
