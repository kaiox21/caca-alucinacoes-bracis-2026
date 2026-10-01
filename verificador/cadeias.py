"""Vocabulário de cadeias de classe processual: sigla e nome por extenso viram o mesmo token.

`AgInt no REsp` e `AgInt no RECURSO ESPECIAL` precisam ser a mesma coisa para que
a resolução desempate candidatos do mesmo número em fases recursais distintas.
O vocabulário foi levantado dos cabeçalhos da base inteira, não do gabarito de
desenvolvimento, e mora fora de `indice/` porque a extração de citações vai
precisar do mesmo mapa.

A ordem dos tokens é a ordem de escrita: o recurso mais recente vem primeiro.
"""
from __future__ import annotations

import re
import unicodedata

# frase normalizada (maiúsculas, sem acento, sem ponto nem hífen) -> tokens
_FRASES: dict[str, tuple[str, ...]] = {}


def _registrar(tokens: str | tuple[str, ...], *frases: str) -> None:
    valor = (tokens,) if isinstance(tokens, str) else tokens
    for frase in frases:
        _FRASES[frase] = valor


# recursos internos e incidentes
_registrar("AGINT", "AGRAVO INTERNO", "AGINT", "AG INT")
_registrar("AGRG", "AGRAVO REGIMENTAL", "AGRG", "AG REG", "AGR")
_registrar("ED", "EMBARGOS DE DECLARACAO", "EDCL", "EMB DECL", "ED", "EDS", "EDCIV")
_registrar("EDV", "EMBARGOS DE DIVERGENCIA", "EDV", "EMB DIV")
_registrar("EINUL", "EMBARGOS INFRINGENTES E DE NULIDADE")
_registrar("EI", "EMBARGOS INFRINGENTES")
_registrar("E", "EMBARGOS", "EMB", "E")
_registrar("AG", "AGRAVO", "AG")
_registrar("QO", "QUESTAO DE ORDEM", "QO")
_registrar("PEXT", "PEDIDO DE EXTENSAO", "PEXT")
_registrar("REF", "REFERENDO")
_registrar("R", "RECURSO", "R")  # a sigla solta aparece no TSE: R-Rp
# STJ e STF
# "AgREsp" e "A.REsp" aplainam para "AG RESP" e "A RESP" (o camel case é partido antes da busca)
_registrar("ARESP", "AGRAVO EM RECURSO ESPECIAL", "ARESP", "AG RESP", "A RESP")
_registrar("RESP", "RECURSO ESPECIAL", "RESP", "REC ESP", "R ESP")
_registrar(("EDV", "RESP"), "ERESP")
_registrar(("EDV", "ARESP"), "EARESP")
_registrar("ARE", "RECURSO EXTRAORDINARIO COM AGRAVO", "ARE")
_registrar("RE", "RECURSO EXTRAORDINARIO", "RE")
_registrar(
    "RHC",
    "RECURSO ORDINARIO EM HABEAS CORPUS",
    "RECURSO ORD EM HABEAS CORPUS",
    "RECURSO EM HABEAS CORPUS",
    "RHC",
    "R H C",
)
_registrar("HC", "HABEAS CORPUS", "HC", "H C")
_registrar(
    "RMS",
    "RECURSO ORDINARIO EM MANDADO DE SEGURANCA",
    "RECURSO ORD EM MANDADO DE SEGURANCA",
    "RECURSO EM MANDADO DE SEGURANCA",
    "RMS",
)
_registrar("MS", "MANDADO DE SEGURANCA", "MS")
_registrar("RCL", "RECLAMACAO", "RCL", "RECL")
_registrar("AR", "ACAO RESCISORIA", "AR")
_registrar("AP", "ACAO PENAL", "AP", "APN")
_registrar("ADI", "ACAO DIRETA DE INCONSTITUCIONALIDADE", "ADI")
_registrar("AC", "ACAO CAUTELAR", "AC")
_registrar("TCA", "TUTELA CAUTELAR ANTECEDENTE")
_registrar("CIC", "CAUTELAR INOMINADA CRIMINAL", "CAUINOMCRIM")
_registrar("SLS", "SUSPENSAO DE LIMINAR E DE SENTENCA", "SLS")
_registrar("SS", "SUSPENSAO DE SEGURANCA", "SS")
_registrar("CC", "CONFLITO DE COMPETENCIA", "CC")
_registrar("PET", "PETICAO", "PET")
# STM
_registrar("APL", "APELACAO", "APL")
_registrar("RSE", "RECURSO EM SENTIDO ESTRITO", "RSE")
_registrar("CJ", "CONFLITO DE JURISDICAO", "CJ")
_registrar("CP", "CORREICAO PARCIAL MILITAR", "CORREICAO PARCIAL")
_registrar("INCOMP", "INCOMPATIBILIDADE")
# TSE
_registrar("ARESPE", "AGRAVO EM RECURSO ESPECIAL ELEITORAL", "ARESPE", "ARESPEL")
_registrar("RESPE", "RECURSO ESPECIAL ELEITORAL", "RESPE", "RESPEL")
_registrar("RO", "RECURSO ORDINARIO ELEITORAL", "RECURSO ORDINARIO", "RO", "ROEL")
_registrar("AI", "AGRAVO DE INSTRUMENTO", "AI")
_registrar("AIJE", "ACAO DE INVESTIGACAO JUDICIAL ELEITORAL", "AIJE")
_registrar("RCED", "RECURSO CONTRA EXPEDICAO DE DIPLOMA", "RCED")
_registrar("RP", "REPRESENTACAO", "RP")
_registrar("PC", "PRESTACAO DE CONTAS", "PC")
_registrar("LT", "LISTA TRIPLICE", "LT")
# TST
_registrar("AIRR", "AGRAVO DE INSTRUMENTO EM RECURSO DE REVISTA", "AIRR")
_registrar("RRAG", "RECURSO DE REVISTA COM AGRAVO", "RRAG")
_registrar("ARR", "ARR")
_registrar("RR", "RECURSO DE REVISTA", "RR")
_registrar("IRR", "INCIDENTE DE RECURSOS DE REVISTA REPETITIVOS", "IRR")
_registrar("ROT", "RECURSO ORDINARIO TRABALHISTA", "ROT")

# Classes que a base de desenvolvimento não tem, mas que os cinco tribunais usam (EXP-011): a
# base da avaliação é outra, e classe fora do vocabulário faz a citação inteira não ser extraída.
# Ficam de fora, de propósito, as classes que só existem abaixo desses tribunais (inquérito policial
# militar, execução penal, cumprimento de sentença, recurso eleitoral): num parecer elas descrevem
# o caso, não um precedente.
# As palavras que só estas frases trazem valem só com inicial maiúscula (`sigla_so_em_maiuscula`):
# `mi`, `ep`, `if`, `ext` e `consulta` em minúscula são palavra comum, não classe.
_ANTES = set(_FRASES)
# STF
_registrar("ADPF", "ARGUICAO DE DESCUMPRIMENTO DE PRECEITO FUNDAMENTAL", "ADPF")
_registrar("ADC", "ACAO DECLARATORIA DE CONSTITUCIONALIDADE", "ADC")
_registrar("ADO", "ACAO DIRETA DE INCONSTITUCIONALIDADE POR OMISSAO", "ADO")
_registrar("ADI", "ADIN")
_registrar("ACO", "ACAO CIVEL ORIGINARIA")  # sem a sigla: o OCR da base parte "ACÓRDÃO" em "ACÓ"
_registrar("AO", "ACAO ORIGINARIA")  # sem a sigla: "Ao" abre frase
_registrar("MI", "MANDADO DE INJUNCAO", "MI")
_registrar("INQ", "INQUERITO", "INQ")
_registrar("EXT", "EXTRADICAO", "EXT")
_registrar("PPE", "PRISAO PREVENTIVA PARA EXTRADICAO", "PPE")
_registrar("HD", "HABEAS DATA", "HD")
_registrar("RVC", "REVISAO CRIMINAL", "RVC", "RVCR")
_registrar("SL", "SUSPENSAO DE LIMINAR", "SL")
_registrar("STA", "SUSPENSAO DE TUTELA ANTECIPADA", "STA")
_registrar("STP", "SUSPENSAO DE TUTELA PROVISORIA", "STP")
_registrar("TPA", "TUTELA PROVISORIA ANTECEDENTE", "TPA")
_registrar("TP", "TUTELA PROVISORIA", "PEDIDO DE TUTELA PROVISORIA", "TP", "TUTPRV")
_registrar("MC", "MEDIDA CAUTELAR", "MC", "MED CAUT")
_registrar("IF", "INTERVENCAO FEDERAL", "IF")
_registrar("CR", "CARTA ROGATORIA")  # sem a sigla: "CR 1988" é a Constituição da República
_registrar("SEC", "SENTENCA ESTRANGEIRA CONTESTADA", "SEC")
_registrar("SE", "SENTENCA ESTRANGEIRA")  # sem a sigla: é UF
_registrar("HDE", "HOMOLOGACAO DE DECISAO ESTRANGEIRA", "HDE")
# STJ
_registrar("PUIL", "PUIL")  # sem o nome por extenso: "LEI" não pode ser palavra de cadeia
_registrar("IDC", "INCIDENTE DE DESLOCAMENTO DE COMPETENCIA", "IDC")
_registrar("IAC", "INCIDENTE DE ASSUNCAO DE COMPETENCIA", "IAC")
_registrar("IRDR", "INCIDENTE DE RESOLUCAO DE DEMANDAS REPETITIVAS", "IRDR")
_registrar("SIRDR", "SUSPENSAO EM INCIDENTE DE RESOLUCAO DE DEMANDAS REPETITIVAS", "SIRDR")
_registrar("CAT", "CONFLITO DE ATRIBUICOES", "CONFLITO DE ATRIBUICAO", "CAT")
_registrar("RCD", "PEDIDO DE RECONSIDERACAO", "RCD")
_registrar("EXEMS", "EXECUCAO EM MANDADO DE SEGURANCA", "EXEMS")
_registrar(("EDV", "AG"), "EAG")
_registrar("QC", "QUEIXA CRIME", "QC")
_registrar("ARGINC", "ARGUICAO DE INCONSTITUCIONALIDADE", "INCIDENTE DE ARGUICAO DE INCONSTITUCIONALIDADE", "ARGINC")
_registrar("EXSUSP", "EXCECAO DE SUSPEICAO", "EXSUSP")
_registrar("CAUINOM", "CAUTELAR INOMINADA", "CAUINOM")
# TST
_registrar("DCG", "DISSIDIO COLETIVO DE GREVE", "DCG")
_registrar("DC", "DISSIDIO COLETIVO", "DC")
_registrar("REENEC", "REEXAME NECESSARIO", "REMESSA NECESSARIA", "REENEC", "REMNEC")
_registrar("AIRO", "AIRO")
_registrar("ROAR", "ROAR")
_registrar("ROMS", "ROMS")
_registrar("RODC", "RODC")
_registrar("ROAG", "ROAG")
_registrar("CP", "CORPAR")
_registrar("TCA", "TUTCAUTANT")
# TSE
_registrar("AIME", "ACAO DE IMPUGNACAO DE MANDATO ELETIVO", "AIME")
_registrar("CTA", "CTA")  # sem o nome por extenso: "Consulta nº 12/2024" também é o que um parecer responde
_registrar("RPP", "REGISTRO DE PARTIDO POLITICO", "RPP")
_registrar("RCAND", "REGISTRO DE CANDIDATURA", "RCAND", "RCAN")
_registrar("RVE", "REVISAO DE ELEITORADO", "RVE")
_registrar("PC", "PRESTACAO DE CONTAS ELEITORAIS", "PRESTACAO DE CONTAS ANUAL")
_registrar("MS", "MSCIV")
_registrar("HC", "HCCRIM")
_registrar("PET", "PETCIV", "PETCRIM")
# STM
_registrar("DESAF", "DESAFORAMENTO", "DESAFORAMENTO DE JULGAMENTO")
_registrar("CJUST", "CONSELHO DE JUSTIFICACAO")
_ORDINAIS = {
    "SEGUNDO": "2", "SEGUNDA": "2", "SEGUNDOS": "2", "SEGUNDAS": "2",
    "TERCEIRO": "3", "TERCEIRA": "3", "TERCEIROS": "3", "TERCEIRAS": "3",
    "QUARTO": "4", "QUARTOS": "4", "QUINTO": "5", "QUINTOS": "5", "SEXTO": "6", "SEXTOS": "6",
    "SETIMO": "7", "SETIMOS": "7", "OITAVO": "8", "OITAVOS": "8", "NONO": "9", "NONOS": "9",
    "DECIMO": "10", "DECIMOS": "10",
}
# conectores e qualificadores que não mudam a identidade da classe
_IGNORAVEIS = {
    "NO", "NA", "NOS", "NAS", "EM", "DE", "DO", "DA", "DOS", "DAS", "A", "O",
    "CRIMINAL", "CIVEL", "ELEITORAL", "MILITAR",
    "SUPERIOR", "TRIBUNAL", "OS", "AS",
}
# "2 os EMBARGOS", "20s EMBARGOS" (OCR de "2os"), "2ºs" e "2ª" (aplainam para "2OS" e "2A"):
# ordinal escrito em algarismo
_ORDINAL_EM_ALGARISMO = re.compile(r"^(\d{1,2}?)[0OA]?S?$")

_POR_PALAVRAS = {tuple(frase.split()): tokens for frase, tokens in _FRASES.items()}
_MAIOR_FRASE = max(len(palavras) for palavras in _POR_PALAVRAS)

# conectores: valem em qualquer caixa e nunca abrem uma cadeia
_CONECTORES = frozenset({"NO", "NA", "NOS", "NAS", "EM", "DE", "DO", "DA", "DOS", "DAS", "A", "O", "OS", "AS", "COM"})
_PALAVRAS = frozenset(
    {palavra for frase in _FRASES for palavra in frase.split()} | set(_ORDINAIS) | _IGNORAVEIS | _CONECTORES
)
# palavras que só o vocabulário do EXP-011 trouxe: no passo relaxado (cadeia em minúscula) não valem
_PALAVRAS_NOVAS = frozenset(
    {palavra for frase in set(_FRASES) - _ANTES for palavra in frase.split()}
    - {palavra for frase in _ANTES for palavra in frase.split()} - set(_ORDINAIS) - _IGNORAVEIS - _CONECTORES
)
# a conjunção "E" dentro de uma frase: (palavra antes, palavra depois), como em
# "EMBARGOS INFRINGENTES E DE NULIDADE" e "SUSPENSAO DE LIMINAR E DE SENTENCA"
_E_DENTRO_DE_FRASE = frozenset(
    (palavras[i - 1], palavras[i + 1])
    for palavras in (frase.split() for frase in _FRASES)
    for i in range(1, len(palavras) - 1)
    if palavras[i] == "E"
)
# ordinal em algarismo com o sufixo colado: "2OS" (de "2ºs" ou "2os"), "3A", "20S" (OCR de "2os")
_ORDINAL_COM_SUFIXO = re.compile(r"^\d{1,2}(?:[OA]S?|0S)$")


def _aplainar(texto: str) -> list[str]:
    # "nosEMBARGOS" -> "nos EMBARGOS", sem quebrar "AgInt" nem "EDcl"
    texto = re.sub(r"(?<=[a-zà-ÿ])(?=[A-ZÀ-Ý]{2,})", " ", texto)
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").upper()
    return re.sub(r"[^A-Z0-9]+", " ", plano).split()


def sem_rn(palavra: str) -> str:
    """`m` escrito como `rn` (RSK-17): só troca se a palavra não for conhecida e a variante for.

    `AGRAVO INTERNO` fica intacto, porque `INTERNO` já é palavra do vocabulário.
    """
    if "RN" not in palavra or palavra in _PALAVRAS:
        return palavra
    variante = palavra.replace("RN", "M")
    return variante if variante in _PALAVRAS else palavra


def normalizar_cadeia(texto: str | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Devolve (tokens, resíduo): os tokens reconhecidos e as palavras que sobraram."""
    if not texto:
        return (), ()
    palavras = [sem_rn(palavra) for palavra in _aplainar(texto)]
    tokens: list[str] = []
    residuo: list[str] = []
    i = 0
    while i < len(palavras):
        for tamanho in range(min(_MAIOR_FRASE, len(palavras) - i), 0, -1):
            achado = _POR_PALAVRAS.get(tuple(palavras[i: i + tamanho]))
            if achado:
                tokens.extend(achado)
                i += tamanho
                break
        else:
            palavra = palavras[i]
            algarismo = _ORDINAL_EM_ALGARISMO.match(palavra)
            if palavra in _ORDINAIS:
                tokens.append(_ORDINAIS[palavra])
            elif algarismo and not tokens:
                tokens.append(algarismo.group(1))
            elif palavra not in _IGNORAVEIS:
                residuo.append(palavra)
            i += 1
    return tuple(tokens), tuple(residuo)


# ---------------------------------------------------------------------- para a extração

def aplainar(texto: str) -> list[str]:
    """As palavras de um trecho, separadas do mesmo jeito que o vocabulário as separa."""
    return _aplainar(texto)


def palavras_de_cadeia() -> frozenset[str]:
    """Toda palavra aplainada que pode compor uma cadeia de classe: das frases, ordinais e conectores."""
    return _PALAVRAS


def sigla_so_em_maiuscula(palavra: str) -> bool:
    """Palavra acrescentada no EXP-011 (`MI`, `EP`, `CONSULTA`): só vale com inicial maiúscula."""
    return palavra in _PALAVRAS_NOVAS


def e_conector(palavra: str) -> bool:
    return palavra in _CONECTORES


def e_ordinal(palavra: str) -> bool:
    """Ordinal por extenso ou em algarismo com sufixo (`TERCEIRO`, `2OS`), já aplainado."""
    return palavra in _ORDINAIS or bool(_ORDINAL_COM_SUFIXO.match(palavra))


def e_ignoravel(palavra: str) -> bool:
    """Conector ou qualificador que não muda a classe (`NO`, `TRIBUNAL`, `ELEITORAL`): nunca abre cadeia."""
    return palavra in _CONECTORES or palavra in _IGNORAVEIS


def e_conjuncao_de_frase(anterior: str, posterior: str) -> bool:
    """O "E" entre `anterior` e `posterior` faz parte de uma frase do vocabulário?"""
    return (anterior, posterior) in _E_DENTRO_DE_FRASE
