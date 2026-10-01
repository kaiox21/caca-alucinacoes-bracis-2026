"""Extração do número do próprio processo de cada acórdão da base, por tribunal.

O número não é coluna da base: está dentro de `texto`, em posição e formato que
mudam por tribunal, e os cabeçalhos têm ruído de OCR próprio. Como a base é
congelada, tratar cada tribunal de forma específica não é overfitting.

Regra de ouro: chave falsa é pior que chave ausente. Um registro indexado pelo
número de outro processo faria uma citação `inventada` resolver como `real`.
Por isso todo CNJ passa pela validação antes de virar chave, e o TST ancora na
frase de abertura do acórdão, nunca na primeira ocorrência de `TST-...`.

No TSE e no STM vale a **primeira âncora na ordem do documento**, seja um número
com marcador (`Nº`), seja um CNJ escrito sem marcador nenhum, que é como parte dos
cabeçalhos do TSE traz o número próprio. O cabeçalho vem antes da ementa, então o
número do processo ganha do número de uma súmula citada.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..cadeias import normalizar_cadeia
from .chaves import SEGMENTO_POR_TRIBUNAL, chave_numerica, so_digitos, validar_cnj

JANELA_CABECALHO = 600
JANELA_ESTENDIDA = 3000

UF_POR_ESTADO = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM", "BAHIA": "BA",
    "CEARA": "CE", "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES", "GOIAS": "GO",
    "MARANHAO": "MA", "MATO GROSSO DO SUL": "MS", "MATO GROSSO": "MT", "MINAS GERAIS": "MG",
    "PARAIBA": "PB", "PARANA": "PR", "PARA": "PA", "PERNAMBUCO": "PE", "PIAUI": "PI",
    "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS",
    "RONDONIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC", "SAO PAULO": "SP",
    "SERGIPE": "SE", "TOCANTINS": "TO",
}
# nomes mais longos primeiro, para "MATO GROSSO DO SUL" não casar como "MATO GROSSO"
_ESTADOS = "|".join(sorted(UF_POR_ESTADO, key=len, reverse=True))


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


@dataclass
class Extracao:
    chaves: list[str] = field(default_factory=list)
    cadeia: str | None = None
    uf: str | None = None
    reprovados: list[tuple[str, str]] = field(default_factory=list)  # (trecho, motivo)
    notas: list[str] = field(default_factory=list)


# "Nº", "N°", "No", "N o" seguidos de dígito. O \b evita casar dentro de "ANO 2016".
_MARCADOR = re.compile(r"\bN\s?[º°oO]\.?\s*(?P<num>\d[\d\s.,\-–—]*)")
# No OCR da base o "º" às vezes some ("N 1588-36...") ou vira outro sinal ("N‚ 374-42...").
# A forma frouxa só vale para CNJ, porque aí a validação do dígito verificador é o filtro.
_MARCADOR_FROUXO = re.compile(r"\bN\s?(?P<sinal>[º°oO‚])?\.?\s*(?P<num>\d[\d\s.,\-–—]*)")
_CNJ_ENTRE_PARENTESES = re.compile(r"^\s*\(\s*(?P<num>\d[\d\s.,\-–—]*)\)")
# CNJ sem marcador, como em "AGRAVO DE INSTRUMENTO 0606871-33.2018.6.19.0000 - RIO DE JANEIRO"
_CNJ_SEM_MARCADOR = re.compile(
    r"(?<![\d.,\-])\d{1,7}\s?-\s?\d{2}\s?[.\s]\s?\d{4}\s?[.\s]\s?\d\s?[.\s]\s?\d{2}\s?[.\s]\s?\d{4}(?!\d)"
)
_UF_APOS_NUMERO = re.compile(r"^\s*[/\-–—(]?\s*(?P<uf>[A-Z]{2})\b")
_MAIUSCULAS_FINAIS = re.compile(r"((?:[A-ZÀ-Ý][A-ZÀ-Ý.]*\s+)+)$")


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip(" .,-–—:")


def _melhor_cnj(trecho: str, tribunal: str, saida: Extracao) -> str | None:
    """Tenta o trecho inteiro e, se falhar, vai descartando pedaços do fim.

    O OCR às vezes cola um número de página depois do CNJ; descartar o resto
    resolve sem afrouxar a validação, que continua sendo o critério de aceite.
    """
    pedacos = trecho.split()
    primeira_falha = None
    while pedacos:
        candidato = " ".join(pedacos)
        if len(so_digitos(candidato)) < 14:
            break
        validacao = validar_cnj(candidato, tribunal)
        if validacao.valido:
            return validacao.cnj.chave
        primeira_falha = primeira_falha or (_limpar(candidato), validacao.motivo)
        pedacos.pop()
    if primeira_falha:
        saida.reprovados.append(primeira_falha)
    return None


def _cadeia_em_maiusculas(antes: str) -> str | None:
    m = _MAIUSCULAS_FINAIS.search(antes.rstrip() + " ")
    return _limpar(m.group(1)) if m else None


def _uf_por_nome(trecho: str) -> str | None:
    achados = re.findall(rf"\b({_ESTADOS})\b", sem_acento(trecho).upper())
    return UF_POR_ESTADO[achados[-1]] if achados else None


# ----------------------------------------------------------------------------- STJ

def extrair_stj(texto: str) -> Extracao:
    saida = Extracao()
    cabecalho = texto[:JANELA_CABECALHO]
    m = _MARCADOR.search(cabecalho)
    if not m:
        return saida
    chave = chave_numerica(m.group("num"))
    if chave and len(chave) <= 9:
        saida.chaves.append(chave)
    antes = cabecalho[: m.start()]
    antes = re.sub(r"Superior Tribunal de Justi[çc]a", " ", antes)
    antes = re.sub(r"Revista Eletr[ôo]nica de Jurisprud[êe]ncia", " ", antes)
    saida.cadeia = _limpar(antes)[-160:] or None
    uf = _UF_APOS_NUMERO.match(cabecalho[m.end():])
    saida.uf = uf.group("uf") if uf else None
    return saida


# ----------------------------------------------------------------------------- STF

_STF_COM_ORGAO = re.compile(
    rf"(?:PRIMEIRA\s+TURMA|SEGUNDA\s+TURMA|PLEN[ÁA]RIO)\s+(?P<cadeia>[^\d]{{3,220}}?)\s+"
    rf"(?P<num>\d[\d.]*\d|\d)\s+(?P<estado>{_ESTADOS})\b"
)
_STF_SEM_ORGAO = re.compile(rf"(?P<num>\d[\d.]*\d)\s+(?P<estado>{_ESTADOS})\b")


def extrair_stf(texto: str) -> Extracao:
    """O STF não usa "Nº": o número vem depois da classe por extenso e antes do estado."""
    saida = Extracao()
    cabecalho = texto[:JANELA_CABECALHO]
    # busca no texto sem acento e em maiúsculas; a cadeia sai desse mesmo texto,
    # porque remover acentos muda o comprimento e os offsets deixam de valer no original
    plano = sem_acento(cabecalho).upper()
    m = _STF_COM_ORGAO.search(plano)
    if m:
        saida.cadeia = _limpar(m.group("cadeia"))
    else:
        m = _STF_SEM_ORGAO.search(plano)
        if not m:
            return saida
        saida.cadeia = _cadeia_em_maiusculas(plano[: m.start("num")])
        saida.notas.append("stf_sem_orgao_julgador")
    chave = chave_numerica(m.group("num"))
    if chave:
        saida.chaves.append(chave)
    saida.uf = UF_POR_ESTADO[m.group("estado")]
    return saida


# ----------------------------------------------------------------------------- STM e TSE


def _ancoras(trecho: str) -> list[tuple[str, re.Match]]:
    """Onde o número do próprio processo pode estar, na ordem do documento."""
    com_marcador = [("marcador", m) for m in _MARCADOR_FROUXO.finditer(trecho)]
    sem_marcador = [("cnj", m) for m in _CNJ_SEM_MARCADOR.finditer(trecho)]
    return sorted(com_marcador + sem_marcador, key=lambda ancora: ancora[1].start())


def _chaves_da_ancora(tipo: str, m: re.Match, trecho: str, tribunal: str, saida: Extracao) -> list[str]:
    if tipo == "cnj":
        validacao = validar_cnj(m.group(), tribunal)
        # sem marcador não há o que reportar: um CNJ de outra justiça no meio do texto
        # é só outro processo citado, não o número próprio que reprovou
        return [validacao.cnj.chave] if validacao.valido else []
    numero = m.group("num")
    digitos = so_digitos(numero)
    if len(digitos) >= 14:
        chave = _melhor_cnj(numero, tribunal, saida)
        if not chave:
            # o número reprovou, mas a classe e a UF do cabeçalho continuam valendo
            # como metadados do registro, que será coberto por exceção curada
            if saida.cadeia is None:
                _metadados(saida, trecho, m, tribunal)
            return []
        return [chave]
    if tribunal == "TSE" and m.group("sinal") in ("º", "°", "o", "O") and 2 <= len(digitos) <= 7:
        # numeração antiga do TSE: sequencial, às vezes com o CNJ entre parênteses
        chaves = [chave_numerica(digitos)]
        extra = _CNJ_ENTRE_PARENTESES.match(trecho[m.end():])
        if extra:
            segunda = _melhor_cnj(extra.group("num"), tribunal, saida)
            if segunda:
                chaves.append(segunda)
        return chaves
    return []


def _cadeia_limpa(cadeia: str | None) -> bool:
    tokens, residuo = normalizar_cadeia(cadeia)
    return bool(tokens) and not residuo


def _guardar_metadados(saida: Extracao, trecho: str, m: re.Match, tribunal: str) -> None:
    """Uma cadeia limpa nunca é trocada por uma pior: o mesmo número aparece em contextos diferentes."""
    if _cadeia_limpa(saida.cadeia):
        candidato = Extracao()
        _metadados(candidato, trecho, m, tribunal)
        if not _cadeia_limpa(candidato.cadeia):
            return
    _metadados(saida, trecho, m, tribunal)


def _melhor_contexto(saida: Extracao, texto: str, tribunal: str) -> None:
    """Procura o mesmo número num contexto melhor, quando a âncora vencedora não trouxe classe.

    Em parte dos registros do TSE o número aparece antes numa capa de sistema
    ("05/12/2020 Número: 0602961-74.2018.6.09.0000") e só depois no cabeçalho do
    acórdão, com a classe. A chave é a mesma; a cadeia e a UF vêm da melhor ocorrência.
    """
    trecho = texto[:JANELA_ESTENDIDA]
    for tipo, m in _ancoras(trecho):
        if _chaves_da_ancora(tipo, m, trecho, tribunal, Extracao()) != saida.chaves:
            continue
        _guardar_metadados(saida, trecho, m, tribunal)
        if _cadeia_limpa(saida.cadeia):
            return


def _extrair_por_marcador(texto: str, tribunal: str) -> Extracao:
    saida = Extracao()
    for janela in (JANELA_CABECALHO, JANELA_ESTENDIDA):
        trecho = texto[:janela]
        for tipo, m in _ancoras(trecho):
            chaves = _chaves_da_ancora(tipo, m, trecho, tribunal, saida)
            if not chaves:
                continue
            saida.chaves.extend(chaves)
            _guardar_metadados(saida, trecho, m, tribunal)
            if not _cadeia_limpa(saida.cadeia):
                _melhor_contexto(saida, texto, tribunal)
            if janela == JANELA_ESTENDIDA:
                saida.notas.append("janela_estendida")
            return saida
    return saida


def _metadados(saida: Extracao, trecho: str, m: re.Match, tribunal: str) -> None:
    antes, depois = trecho[: m.start()], trecho[m.end(): m.end() + 160]
    if tribunal == "TSE":
        saida.cadeia = _cadeia_tse(antes)
        saida.uf = _uf_por_nome(re.split(r"Relator", depois, maxsplit=1, flags=re.I)[0])
    else:
        saida.cadeia = _cadeia_em_maiusculas(antes)
        uf = _UF_APOS_NUMERO.match(depois)
        saida.uf = uf.group("uf") if uf else None


def _cadeia_tse(antes: str) -> str | None:
    # "ACÓRDÃO" aparece também como "ACORDAO" e "AC€RD O" no OCR da base
    partes = re.split(r"AC.{0,2}RD.{0,2}O\b|TRIBUNAL\s+SUPERIOR\s+ELEITORAL?", antes)
    resto = _limpar(partes[-1])
    return resto[-200:] or None


def extrair_stm(texto: str) -> Extracao:
    return _extrair_por_marcador(texto, "STM")


def extrair_tse(texto: str) -> Extracao:
    return _extrair_por_marcador(texto, "TSE")


# ----------------------------------------------------------------------------- TST

_TST_NUMERO = r"TST\s*-\s*(?P<cadeia>(?:[A-Za-z]+\s*-\s*)+)(?P<num>\d[\d\s]*-\s*[\d\s.]{10,30}\d)"
_TST_ABERTURA = re.compile(
    r"(?:estes|destes|os\s+presentes)\s+autos.{0,220}?" + _TST_NUMERO, re.S | re.I
)
_TST_QUALQUER = re.compile(_TST_NUMERO)


def extrair_tst(texto: str) -> Extracao:
    """Ancora na frase de abertura ("estes autos de ... nº TST-<cadeia>-<CNJ>").

    197 dos 198 acórdãos citam outros processos, e a ementa vem antes da
    abertura: a primeira ocorrência de `TST-...` pode ser um precedente.
    """
    saida = Extracao()
    abertura = None
    for m in _TST_ABERTURA.finditer(texto):
        chave = _melhor_cnj(m.group("num"), "TST", saida)
        if chave:
            abertura = (chave, m.group("cadeia"))
            break
    primeira = None
    descartados = Extracao()
    for m in _TST_QUALQUER.finditer(texto):
        chave = _melhor_cnj(m.group("num"), "TST", descartados)
        if chave:
            primeira = (chave, m.group("cadeia"))
            break
    escolhida = abertura or primeira
    if escolhida is None:
        return saida
    if abertura is None:
        saida.notas.append("tst_sem_frase_de_abertura")
    elif primeira and primeira[0] != abertura[0]:
        saida.notas.append(f"tst_ancora_divergente:primeira_ocorrencia={primeira[0]}")
    saida.chaves.append(escolhida[0])
    saida.cadeia = re.sub(r"\s+", "", escolhida[1]).strip("-")
    return saida


EXTRATORES = {
    "STF": extrair_stf,
    "STJ": extrair_stj,
    "STM": extrair_stm,
    "TSE": extrair_tse,
    "TST": extrair_tst,
}

assert set(SEGMENTO_POR_TRIBUNAL) <= set(EXTRATORES)
