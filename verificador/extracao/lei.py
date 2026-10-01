"""Artigo de lei: `art.`/`artigo` + número + incisos, parágrafos e alíneas + diploma.

A palavra-chave é fechada, o diploma não: os 9 diplomas da base entram por apelido e por
número, e a forma numerada (`Lei nº …/AAAA`, `Lei Complementar nº …`, `Decreto-Lei nº …`),
`Código …` e `Estatuto …` ficam abertos a qualquer número ou nome. Diploma que não está
na base é `inventada` (FR-03), sem risco de τ. Inciso, parágrafo e alínea entram no span
e não na chave (FR-10). O ordinal do artigo (`5º`, `5o`) nunca é lido como dígito.
"""
from __future__ import annotations

import re

from .achado import Achado
from .tolerancia import tolerante

_ARTIGO = r"\b(?:[Aa]rt(?:igo)?|ART(?:IGO)?)\.?\s*"
# "1.134", e com o ruído de formatação do número: "1 134", "1. 134", "1.-⏎134"
_NUMERO = (r"(?P<art>\d{1,4}(?:(?:[ \t]*\.[ \t]*-?\n?[ \t]*|[ \t]+)\d{3}(?!\d))*)"
           r"(?:\s*[ºª](?!\w)|o(?![A-Za-zÀ-ÿ0-9]))?(?:-(?P<letra>[A-Z])(?![A-Za-z]))?")
# o que vem entre o artigo e o diploma: "caput", inciso, parágrafo, alínea, soltos ou em lista
# ("incisos I e II", "III, a e c"). Só vale se o diploma vier logo depois, e é isso que segura
# a alínea sem aspas: uma letra solta depois de vírgula não vira complemento em texto corrido.
_ASPAS = "['\"‘’“”]"
_ITEM = (
    rf"(?:caput|[IVXLC]+(?![A-Za-z])|§§?\s*\d+\s*º?(?:-[A-Z])?(?:\s+e\s+\d+\s*º?(?:-[A-Z])?)?|par[áa]grafos?\s+(?:[úu]nico|\d+\s*º?)"
    rf"|incisos?\s+[IVXLC]+(?![A-Za-z])|al[íi]neas?\s+{_ASPAS}?[a-z]{_ASPAS}?(?![A-Za-zÀ-ÿ])"
    rf"|{_ASPAS}[a-z]{_ASPAS}|[a-z]\)|[a-z](?![A-Za-zÀ-ÿ0-9]))"
)
_COMPLEMENTO = rf"(?:\s*,\s*{_ITEM}(?:\s+e\s+{_ITEM})*)*"
_LIGACAO = r",?\s+d[aoe]s?\s+"
_NOME = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ]*"
_CONECTIVO = r"(?:de|do|da|dos|das|e)"
# o número da norma aceita o mesmo ruído de formatação do número de processo: "5. 452" e "8.-⏎078";
# a quebra de linha só vale depois de ponto ou hífen, para não colar o número a uma linha que começa por dígito
_QUEBRA_NO_NUMERO = r"(?:[ \t]|(?<=\.)-?\n[ \t]*|-\n[ \t]*)"
_NUMERO_DA_NORMA = rf"(?:\s+[nN]\.?[º°oO.]?\.?)?\s*\d[\d.]*(?:{_QUEBRA_NO_NUMERO}\d{{3}}(?!\d))*(?:\s*/\s*\d{{2,4}})?"
# leis conhecidas pelo nome, sem número: só as que `normalizar_diploma` sabe a que diploma levam
_LEIS_PELO_NOME = [
    "Lei das Eleições", "Lei de Inelegibilidades", "Lei de Inelegibilidade", "Lei dos Partidos Políticos",
    "Lei de Improbidade Administrativa", "Lei de Execução Penal", "Lei de Execuções Penais",
    "Lei de Introdução às Normas do Direito Brasileiro", "Lei da Ficha Limpa", "Lei de Responsabilidade Fiscal",
    "Lei Orgânica da Magistratura Nacional", "Lei Maria da Penha", "Lei de Drogas", "Lei de Execução Fiscal",
    "Lei do Mandado de Segurança", "Lei da Ação Civil Pública", "Lei de Crimes Hediondos",
    "Lei dos Crimes Hediondos", "Lei de Crimes Ambientais", "Lei de Falências", "Lei de Arbitragem",
    "Lei do Inquilinato", "Lei dos Juizados Especiais", "Lei Anticorrupção", "Lei Geral de Proteção de Dados",
    "Marco Civil da Internet", "Lei de Acesso à Informação", "Lei de Abuso de Autoridade",
]
_ANO_DO_DIPLOMA = r"(?:\s+de\s+(?:1[89]|20)\d{2}(?!\d))?"  # "Código Civil de 2002", "Constituição de 1988"
_DIPLOMA = "|".join([
    rf"{tolerante('Lei')}\s+{tolerante('Complementar')}{_NUMERO_DA_NORMA}",
    rf"{tolerante('Decreto')}\s*-?\s*{tolerante('Lei')}{_NUMERO_DA_NORMA}",
    rf"{tolerante('Lei')}{_NUMERO_DA_NORMA}",
    rf"(?:{tolerante('Decreto')}|{tolerante('Emenda')}\s+{tolerante('Constitucional')}"
    rf"|{tolerante('Medida')}\s+{tolerante('Provisória')}|LC|EC|MP)(?![A-Za-zÀ-ÿ]){_NUMERO_DA_NORMA}",
    rf"{tolerante('Constituição')}(?:\s+(?:{tolerante('Federal')}|da\s+{tolerante('República')}|{tolerante('Estadual')}))?{_ANO_DO_DIPLOMA}",
    rf"{tolerante('Consolidação')}\s+das\s+{tolerante('Leis')}\s+do\s+{tolerante('Trabalho')}",
    rf"(?:{tolerante('Código')}|{tolerante('Estatuto')})(?:\s+(?:{_CONECTIVO}\s+)?{_NOME})+{_ANO_DO_DIPLOMA}",
    "|".join(r"\s+".join(tolerante(palavra) for palavra in nome.split()) for nome in _LEIS_PELO_NOME),
    r"(?:CRFB|CPPM|LINDB|LOMAN|LGPD|CF|CLT|CPC|CPP|CPM|CDC|CTN|CTB|ECA|LEP|LRF|CC|CP)(?![A-Za-z])(?:\s*/\s*\d{2,4})?",
])
_LEI = re.compile(rf"{_ARTIGO}{_NUMERO}{_COMPLEMENTO}{_LIGACAO}(?P<diploma>{_DIPLOMA})")


# nomes por extenso que a normalização de diplomas conhece; o ruído de letra é desfeito aqui
_NOMES_CONHECIDOS = [
    "Constituição Federal", "Constituição da República", "Constituição",
    "Consolidação das Leis do Trabalho", "Código de Processo Civil", "Código de Processo Penal Militar",
    "Código de Processo Penal", "Código Penal Militar", "Código Penal", "Código Civil",
    "Código de Defesa do Consumidor", "Código Eleitoral",
    "Código Tributário Nacional", "Código de Trânsito Brasileiro", "Estatuto da Criança e do Adolescente",
    *_LEIS_PELO_NOME,
]
_NOMES = [(re.compile(r"\s+".join(tolerante(p) for p in nome.split()) + r"(?:\s+de\s+(?P<ano>\d{4}))?"), nome)
          for nome in _NOMES_CONHECIDOS]
_NUMERADA = re.compile(
    rf"(?P<tipo>{tolerante('Lei')}\s+{tolerante('Complementar')}|{tolerante('Decreto')}\s*-?\s*{tolerante('Lei')}|{tolerante('Lei')}"
    rf"|{tolerante('Decreto')}|{tolerante('Emenda')}\s+{tolerante('Constitucional')}|{tolerante('Medida')}\s+{tolerante('Provisória')}|LC|EC|MP)"
    rf"(?:\s+[nN]\.?[º°oO.]?\.?)?\s*(?P<num>\d[\d.]*(?:-?[ \t]\d{{3}}(?!\d))*)(?:\s*/\s*(?P<ano>\d{{2,4}}))?"
)


def _nome_do_tipo(tipo: str) -> str:
    """O tipo da norma como `normalizar_diploma` espera, com o ruído de letra desfeito."""
    plano = re.sub(r"[\s-]+", " ", tipo).strip().lower()
    if plano in ("lc", "ec", "mp"):
        return {"lc": "Lei Complementar", "ec": "Emenda Constitucional", "mp": "Medida Provisória"}[plano]
    inicial = plano[0]
    if inicial == "l":
        return "Lei Complementar" if " " in plano else "Lei"
    if inicial == "d":
        return "Decreto-Lei" if " " in plano else "Decreto"
    return "Emenda Constitucional" if inicial == "e" else "Medida Provisória"


def _diploma_canonico(diploma: str) -> str:
    """O diploma com o ruído de letra desfeito, na forma que `normalizar_diploma` reconhece."""
    diploma = re.sub(r"\s+", " ", diploma).strip()
    numerada = _NUMERADA.fullmatch(diploma)
    if numerada:
        nome = _nome_do_tipo(numerada.group("tipo"))
        ano = f"/{numerada.group('ano')}" if numerada.group("ano") else ""
        numero = re.sub(r"[ \t-]", "", numerada.group("num"))  # "5. 452", "5.-⏎452" e "5.452" são a mesma norma
        return f"{nome} nº {numero}{ano}"
    for padrao, nome in _NOMES:
        m = padrao.fullmatch(diploma)
        if m:  # o ano fica: "Código de Processo Civil de 1973" não é o código em vigor
            return f"{nome} de {m.group('ano')}" if m.group("ano") else nome
    return diploma


def extrair_leis(texto: str) -> list[Achado]:
    """Citações a artigo de lei do texto normalizado."""
    return [
        # o artigo com letra ("896-A") é outro artigo: a letra vai junto para a consulta
        Achado(m.start(), m.end(), "lei", m.span("art"),
               numero=re.sub(r"\D", "", m.group("art")) + (f"-{m.group('letra')}" if m.group("letra") else ""),
               diploma=_diploma_canonico(m.group("diploma")))
        for m in _LEI.finditer(texto)
    ]
