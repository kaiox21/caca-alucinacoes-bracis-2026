"""Citações a processo: âncora no número, cadeia de classe crescendo para a esquerda.

A partir de cada número, anda para a esquerda enquanto as palavras pertencem ao
vocabulário de cadeias de classe (`verificador/cadeias.py`, levantado dos cabeçalhos
da base, não do dev: RSK-01). A caminhada é larga de propósito; o início do span é o
**maior trecho final** dela que normaliza sem resíduo e começa numa palavra que abre
cadeia. Sem token de classe, o número não é citação de processo: é o que afasta os
distratores oficiais (autos do próprio documento, protocolo, OAB, fls., valor da causa).

Guardas de forma, porque cadeia errada em grupo de colisão vira `incompleta` (DEC-020):
palavra de conteúdo só com inicial maiúscula; `E` só colado por hífen (`E-ED-RR`) ou
dentro de uma frase registrada (`Embargos Infringentes e de Nulidade`), nunca como a
conjunção entre duas citações; `A` só abre cadeia seguido de ponto (`A.REsp`, nunca o artigo); e a
caminhada não entra no número nem na UF da citação anterior (AC, AP, MS, RO e RR são
UF e também sigla de classe).
"""
from __future__ import annotations

import re

from ..cadeias import (
    aplainar, e_conjuncao_de_frase, e_ignoravel, e_ordinal, palavras_de_cadeia, sem_rn, sigla_so_em_maiuscula,
)
from ..indice.extratores import UF_POR_ESTADO, sem_acento
from ..resolucao import normalizar_cadeia_citada
from .achado import Achado
from .numeros import Numero, achar_numeros

UFS = frozenset("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
_UF = re.compile(
    r"[ \t]*\n?[ \t]*(?:(?P<abre>\()|/|-)[ \t]*\n?[ \t]*(?P<uf>[A-Z]{2})(?![A-Za-z0-9])(?(abre)[ \t]*\))"
)
# o STF escreve a UF por extenso no cabeçalho ("68.244 SÃO PAULO"), e uma citação pode copiar
_ESTADOS = "|".join(sorted(UF_POR_ESTADO, key=len, reverse=True))
_UF_POR_EXTENSO = re.compile(rf"[ \t]*\n?[ \t]*(?:[-/][ \t]*)?(?P<estado>{_ESTADOS})\b", re.IGNORECASE)
_PALAVRA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9ºª]+")
_LIGACAO = re.compile(r"[ \t\n.\-]*")  # o que pode ligar duas palavras da mesma cadeia
_MARCADORES = frozenset({"N", "NO"})  # nº, n°, n., No aplainam para NO ou N
_SUFIXOS_DE_ORDINAL = frozenset({"O", "OS", "A", "AS"})  # "2 os EMBARGOS"
_PREFIXO_DE_PROCESSO = re.compile(r"processo\s+n\.?[º°o]?\.?\s", re.IGNORECASE)
_MAX_PALAVRAS = 24
_MAX_RECUO = 300


def _colada_por_hifen(texto: str, inicio: int, fim: int) -> bool:
    """`E-ED-RR`, `TST- ED - E-ED`: o vizinho imediato, pulando só espaços, é um hífen."""
    esquerda = texto[max(0, inicio - 4):inicio].rstrip(" \t")
    direita = texto[fim:fim + 4].lstrip(" \t")
    return esquerda.endswith("-") or direita.startswith("-")


def _aceitavel(texto: str, inicio: int, fim: int, a_direita: str | None, a_esquerda: str | None,
               relaxado: bool = False) -> bool:
    """A palavra `texto[inicio:fim]` pode fazer parte de uma cadeia de classe?

    No passo relaxado a guarda de caixa cai (`DEC-023`, emendada): a cadeia em minúscula
    ainda delimita o span, e quem não a aceita é o desempate.
    """
    palavra = texto[inicio:fim]
    partes = [sem_rn(parte) for parte in aplainar(palavra)]  # "Rnandado" vale como "Mandado" (RSK-17)
    if not partes:
        return False
    if len(partes) == 1 and partes[0].isdigit():
        # algarismo solto só como ordinal seguido de "os"/"as": "2 os EMBARGOS"
        return len(partes[0]) <= 2 and a_direita in _SUFIXOS_DE_ORDINAL
    for i, parte in enumerate(partes):
        if parte in _MARCADORES or parte == "PROCESSO" or e_ignoravel(parte):
            continue
        if parte == "E":  # Embargos colado por hífen, ou a conjunção de uma frase registrada
            if not (_colada_por_hifen(texto, inicio, fim) or e_conjuncao_de_frase(a_esquerda or "", a_direita or "")):
                return False
            continue
        if not (e_ordinal(parte) or parte in palavras_de_cadeia() or parte == "TST"):
            return False
        # conteúdo só com inicial maiúscula; as partes depois da primeira vêm do camel case
        if i == 0 and not (relaxado or palavra[0].isupper() or palavra[0].isdigit()):
            return False
        if i == 0 and relaxado and sigla_so_em_maiuscula(parte) and not palavra[0].isupper():
            return False  # "mi 100", "ep 12", "ext 123": palavra comum, não classe
    return True


def _abre_cadeia(texto: str, inicio: int, fim: int, relaxado: bool = False) -> bool:
    primeira = sem_rn(aplainar(texto[inicio:fim])[0])
    if relaxado and primeira in ("E", "A"):
        return False  # a conjunção e o artigo seguem fora, mesmo no passo relaxado
    if primeira == "A":
        return texto[fim:fim + 1] == "."  # A.REsp, nunca o artigo "a"
    if primeira == "PROCESSO":  # só o prefixo "Processo nº TST-…", não a palavra solta
        return _PREFIXO_DE_PROCESSO.match(texto, inicio) is not None
    if primeira == "TST":  # só o prefixo "TST-RR-…": em "o TST no RR-…" o tribunal fica fora do span
        return texto[fim:fim + 3].lstrip(" \t").startswith("-")
    return not (primeira in _MARCADORES or e_ignoravel(primeira) or primeira in {"STJ", "STF", "TSE", "STM"})


def _palavras_a_esquerda(texto: str, fim: int, barreira: int, relaxado: bool = False) -> list[tuple[int, int]]:
    """Palavras aceitáveis numa cadeia, da mais próxima do número para a mais distante."""
    janela_inicio = max(barreira, fim - _MAX_RECUO)
    palavras = list(_PALAVRA.finditer(texto, janela_inicio, fim))
    aceitas: list[tuple[int, int]] = []
    cursor = fim
    a_direita = None
    for k in range(len(palavras) - 1, -1, -1):
        m = palavras[k]
        ligacao = texto[m.end():cursor]
        if _LIGACAO.fullmatch(ligacao) is None or ligacao.count("\n") > 1:
            break
        # "2. O REsp …": o número de um parágrafo, e não o ordinal de "2 os Embargos"
        if m.group().isdigit() and "." in ligacao:
            break
        a_esquerda = aplainar(palavras[k - 1].group())[-1] if k else None
        if not _aceitavel(texto, m.start(), m.end(), a_direita, a_esquerda, relaxado):
            break
        aceitas.append(m.span())
        a_direita = aplainar(m.group())[-1]
        cursor = m.start()
        if len(aceitas) == _MAX_PALAVRAS:
            break
    return aceitas


def inicio_da_cadeia(texto: str, fim: int, barreira: int = 0, relaxado: bool = False) -> int | None:
    """Início da cadeia de classe que termina em `fim`: o maior trecho final que normaliza sem resíduo.

    Serve ao processo (a cadeia antes do número) e à descritiva (a classe antes do ano).
    """
    palavras = _palavras_a_esquerda(texto, fim, barreira, relaxado)
    for inicio, fim_da_palavra in reversed(palavras):  # do mais distante para o mais próximo
        if not _abre_cadeia(texto, inicio, fim_da_palavra, relaxado):
            continue
        tokens, residuo = normalizar_cadeia_citada(texto[inicio:fim])
        if tokens and not residuo and tokens != ("R",):  # "R" solto nunca autoriza (R$ …)
            return inicio
    return None


def _e_ano_de_descritiva(texto: str, numero: Numero, barreira: int) -> bool:
    """`Rcl de 2021`: ano depois de "de"/"em" é o molde descritivo, que tem família própria."""
    if len(numero.digitos) != 4 or not 1900 <= int(numero.digitos) <= 2100:
        return False
    palavras = _palavras_a_esquerda(texto, numero.inicio, barreira)
    return bool(palavras) and aplainar(texto[slice(*palavras[0])])[-1] in {"DE", "EM", "DO", "DA"}


def _tem_marcador(texto: str, numero: Numero, barreira: int) -> bool:
    palavras = _palavras_a_esquerda(texto, numero.inicio, barreira)
    return bool(palavras) and aplainar(texto[slice(*palavras[0])])[-1] in _MARCADORES


def extrair_processos(texto: str) -> list[Achado]:
    """Citações a processo do texto normalizado, com número e cadeia separados."""
    achados = []
    barreira = 0
    for numero in achar_numeros(texto):
        fim = numero.fim
        uf = _UF.match(texto, fim)
        por_extenso = _UF_POR_EXTENSO.match(sem_acento(texto).upper(), fim)
        if uf and uf.group("uf") in UFS:
            fim = uf.end()
        elif por_extenso:
            fim = por_extenso.end()
        # número curto só com marcador ("nº 87") ou com UF colada ("87 - DF"): sozinho não é citação
        pode = len(numero.digitos) >= 3 or _tem_marcador(texto, numero, barreira) or fim > numero.fim
        if pode and not _e_ano_de_descritiva(texto, numero, barreira):
            inicio = inicio_da_cadeia(texto, numero.inicio, barreira)
            confiavel = inicio is not None
            if inicio is None:  # segunda tentativa, aceitando cadeia em minúscula (DEC-023)
                inicio = inicio_da_cadeia(texto, numero.inicio, barreira, relaxado=True)
            if inicio is not None:
                achados.append(Achado(inicio, fim, "processo", (numero.inicio, numero.fim),
                                      numero=numero.digitos, cadeia=texto[inicio:numero.inicio],
                                      cadeia_confiavel=confiavel))
                barreira = fim  # a próxima cadeia não entra nesta citação nem na UF dela
    return achados
