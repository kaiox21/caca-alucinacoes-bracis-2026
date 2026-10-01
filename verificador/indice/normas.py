"""Chaves de súmulas e de dispositivos de lei.

Súmula: (tribunal, vinculante, número). `Vinculante` faz parte da chave (DEC-013).
Dispositivo: (diploma, artigo), com o diploma normalizado por tipo e número,
porque a base nunca usa apelido (FR-08): o CPC aparece como `Lei nº 13.105`.
"""
from __future__ import annotations

import re
import unicodedata

ChaveSumula = tuple[str, bool, int]
ChaveDiploma = tuple[str, str]  # (tipo, número); a Constituição é ("constituicao", "1988")

_SUMULA = re.compile(r"S[úu]mula\s+(?P<vinc>Vinculante\s+)?n\.?\s*(?P<num>\d+)\s+do\s+(?P<trib>\w+)", re.I)
_ARTIGO_DA_BASE = re.compile(
    r"Artigo\s+(?P<art>[\d.]+)\s*[º°o]?(?:\s*-\s*(?P<letra>[A-Za-z]))?\s+d[aoe]\s+(?P<diploma>[^\n]+)", re.I
)

CONSTITUICAO: ChaveDiploma = ("constituicao", "1988")

# apelido normalizado -> diploma. Os mais longos são testados primeiro, para
# "codigo de processo penal militar" não casar como "codigo de processo penal".
_APELIDOS: dict[str, ChaveDiploma] = {
    "constituicao federal": CONSTITUICAO,
    "constituicao da republica": CONSTITUICAO,
    "constituicao": CONSTITUICAO,
    "crfb": CONSTITUICAO,
    "cf": CONSTITUICAO,
    "consolidacao das leis do trabalho": ("decreto-lei", "5452"),
    "clt": ("decreto-lei", "5452"),
    "codigo de processo civil": ("lei", "13105"),
    "cpc": ("lei", "13105"),
    "codigo de processo penal militar": ("decreto-lei", "1002"),
    "cppm": ("decreto-lei", "1002"),
    "codigo de processo penal": ("decreto-lei", "3689"),
    "cpp": ("decreto-lei", "3689"),
    "codigo penal militar": ("decreto-lei", "1001"),
    "cpm": ("decreto-lei", "1001"),
    "codigo penal": ("decreto-lei", "2848"),
    "cp": ("decreto-lei", "2848"),
    "codigo civil": ("lei", "10406"),
    "cc": ("lei", "10406"),
    "codigo de defesa do consumidor": ("lei", "8078"),
    "cdc": ("lei", "8078"),
    "codigo eleitoral": ("lei", "4737"),
    "lei das eleicoes": ("lei", "9504"),
    "lei de inelegibilidades": ("lei complementar", "64"),
    "lei de inelegibilidade": ("lei complementar", "64"),
    # diplomas que a base de desenvolvimento não tem, mas que a da avaliação pode ter (EXP-011).
    # O apelido só decide alguma coisa se o diploma estiver na base: sem registro, segue `inventada`.
    "codigo tributario nacional": ("lei", "5172"),
    "ctn": ("lei", "5172"),
    "codigo de transito brasileiro": ("lei", "9503"),
    "ctb": ("lei", "9503"),
    "estatuto da crianca e do adolescente": ("lei", "8069"),
    "eca": ("lei", "8069"),
    "estatuto do idoso": ("lei", "10741"),
    "estatuto da advocacia": ("lei", "8906"),
    "estatuto do desarmamento": ("lei", "10826"),
    "estatuto dos militares": ("lei", "6880"),
    "estatuto da cidade": ("lei", "10257"),
    "codigo florestal": ("lei", "12651"),
    "codigo brasileiro de aeronautica": ("lei", "7565"),
    "lei de execucao penal": ("lei", "7210"),
    "lei de execucoes penais": ("lei", "7210"),
    "lep": ("lei", "7210"),
    "lei de improbidade administrativa": ("lei", "8429"),
    "lei dos partidos politicos": ("lei", "9096"),
    "lei de introducao as normas do direito brasileiro": ("decreto-lei", "4657"),
    "lindb": ("decreto-lei", "4657"),
    "lei da ficha limpa": ("lei complementar", "135"),
    "lei de responsabilidade fiscal": ("lei complementar", "101"),
    "lrf": ("lei complementar", "101"),
    "lei organica da magistratura nacional": ("lei complementar", "35"),
    "loman": ("lei complementar", "35"),
    "lei maria da penha": ("lei", "11340"),
    "lei de drogas": ("lei", "11343"),
    "lei de execucao fiscal": ("lei", "6830"),
    "lei do mandado de seguranca": ("lei", "12016"),
    "lei da acao civil publica": ("lei", "7347"),
    "lei de crimes hediondos": ("lei", "8072"),
    "lei dos crimes hediondos": ("lei", "8072"),
    "lei de crimes ambientais": ("lei", "9605"),
    "lei de falencias": ("lei", "11101"),
    "lei de arbitragem": ("lei", "9307"),
    "lei do inquilinato": ("lei", "8245"),
    "lei dos juizados especiais": ("lei", "9099"),
    "lei anticorrupcao": ("lei", "12846"),
    "lei geral de protecao de dados": ("lei", "13709"),
    "lgpd": ("lei", "13709"),
    "marco civil da internet": ("lei", "12965"),
    "lei de acesso a informacao": ("lei", "12527"),
    "lei de abuso de autoridade": ("lei", "13869"),
}
# o mesmo apelido com outro ano é outro diploma: `CPC/1973` não é a Lei nº 13.105, e marcar
# como `real` o artigo de um código revogado seria o erro mais caro da métrica
_OUTRA_EDICAO: dict[ChaveDiploma, dict[str, ChaveDiploma | None]] = {
    ("lei", "13105"): {"73": ("lei", "5869"), "1973": ("lei", "5869"), "39": None, "1939": None},
    ("lei", "10406"): {"16": ("lei", "3071"), "1916": ("lei", "3071")},
    CONSTITUICAO: {ano: None for ano in ("1824", "1891", "1934", "1937", "1946", "1967", "1969", "34", "37", "46", "67", "69")},
}
_ANO_DO_APELIDO = re.compile(r"(?:/| de )\s*(?P<ano>\d{2,4})\b")
_APELIDOS_ORDENADOS = sorted(_APELIDOS, key=len, reverse=True)

_NUMERADO = re.compile(
    r"\b(?P<tipo>lei complementar|decreto lei|decreto|emenda constitucional|medida provisoria|lei|lc|dl|ec|mp)"
    r"\s*(?:n\s?[o0]?\s+)?(?P<num>\d+)"
)
_TIPOS = {"lei complementar": "lei complementar", "lc": "lei complementar",
          "decreto lei": "decreto-lei", "dl": "decreto-lei", "lei": "lei", "decreto": "decreto",
          "emenda constitucional": "emenda constitucional", "ec": "emenda constitucional",
          "medida provisoria": "medida provisoria", "mp": "medida provisoria"}


def _plano(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"(?<=\d)\.(?=\d)", "", s)  # 13.105 -> 13105
    return re.sub(r"[^a-z0-9/]+", " ", s).strip()


def normalizar_diploma(texto: str) -> ChaveDiploma | None:
    """Aceita `Lei nº 13.105/2015`, `CPC`, `Constituição da República`, `LC 64/90`."""
    plano = _plano(texto)
    m = _NUMERADO.search(plano)
    if m:
        return _TIPOS[m.group("tipo")], m.group("num").lstrip("0")
    for apelido in _APELIDOS_ORDENADOS:
        achado = re.search(rf"\b{apelido}\b", plano)
        if achado:
            diploma = _APELIDOS[apelido]
            ano = _ANO_DO_APELIDO.match(plano, achado.end())
            if ano and ano.group("ano") in _OUTRA_EDICAO.get(diploma, {}):  # edição anterior: outro diploma
                return _OUTRA_EDICAO[diploma][ano.group("ano")]
            return diploma
    return None


def letra_do_artigo(artigo: str | int) -> str:
    """`896-A` e `5º-B` têm letra; `896, § 1º-A` não: a letra do parágrafo não é do artigo."""
    if isinstance(artigo, int):
        return ""
    m = re.match(r"\s*(?:art(?:igo)?\.?\s*)?\d[\d.]*\s*[º°o]?\s*-\s*([A-Za-z])(?![A-Za-zÀ-ÿ])", artigo, re.I)
    return m.group(1).upper() if m else ""


def numero_do_artigo(artigo: str | int) -> int | None:
    """`art. 1.134`, `7º, XXIX` e `93, IX` viram 1134, 7 e 93: inciso e parágrafo não contam."""
    if isinstance(artigo, int):
        return artigo
    m = re.search(r"\d[\d.]*", artigo)
    return int(m.group(0).replace(".", "")) if m else None


def chave_de_sumula_da_base(texto: str) -> ChaveSumula | None:
    m = _SUMULA.match(texto)
    if not m:
        return None
    return m.group("trib").upper(), bool(m.group("vinc")), int(m.group("num"))


def chave_de_dispositivo_da_base(texto: str) -> tuple[ChaveDiploma, int | str] | None:
    """(diploma, artigo). O artigo com letra (`896-A`) é outro artigo, e a chave dele é `"896A"`."""
    m = _ARTIGO_DA_BASE.match(texto)
    if not m:
        return None
    diploma = normalizar_diploma(m.group("diploma"))
    artigo = numero_do_artigo(m.group("art"))
    if diploma is None or artigo is None:
        return None
    return diploma, f"{artigo}{m.group('letra').upper()}" if m.group("letra") else artigo
