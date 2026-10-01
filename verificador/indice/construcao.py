"""Construção do índice canônico a partir de `desafio1_bracis.db`.

O índice é montado em memória a cada execução (leva menos de um segundo), sem
rede e de forma determinística. Falha ruidosa: acórdão sem chave válida, ou
exceção curada apontando para registro inexistente, interrompe a construção.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from itertools import combinations
from pathlib import Path

from ..cadeias import normalizar_cadeia
from .chaves import chave_numerica, so_digitos
from .extratores import EXTRATORES
from .normas import (
    ChaveDiploma,
    ChaveSumula,
    chave_de_dispositivo_da_base,
    chave_de_sumula_da_base,
    letra_do_artigo,
    normalizar_diploma,
    numero_do_artigo,
)

EXCECOES_PADRAO = Path(__file__).with_name("excecoes.toml")
TAMANHO_DA_ASSINATURA = 300


class ErroDeConstrucao(RuntimeError):
    """A base não pôde ser indexada por inteiro; a mensagem nomeia os registros."""


@dataclass(frozen=True)
class Candidato:
    id: int
    documento_id: str
    natureza: str
    tribunal: str | None
    ano: int | None
    relator: str | None
    uf: str | None = None
    cadeia: str | None = None
    cadeia_normalizada: tuple[str, ...] = ()
    # só fazem sentido dentro do resultado de uma consulta por número
    duplicata: bool = False
    canonico: bool = False


@dataclass
class Relatorio:
    cobertura: dict[str, tuple[int, int]] = field(default_factory=dict)
    chaves_por_registro: dict[int, int] = field(default_factory=dict)
    colisoes_duplicatas: list[tuple[str, list[str]]] = field(default_factory=list)
    colisoes_distintas: list[tuple[str, list[str]]] = field(default_factory=list)
    cnj_reprovados: list[tuple[str, str, str]] = field(default_factory=list)
    ancoras_tst_divergentes: list[tuple[str, str]] = field(default_factory=list)
    janela_estendida: list[str] = field(default_factory=list)
    excecoes_usadas: list[tuple[str, str, str]] = field(default_factory=list)
    cadeias_sem_normalizacao: list[tuple[str, str, str]] = field(default_factory=list)
    sumulas: int = 0
    dispositivos: int = 0

    @property
    def acordaos_indexados(self) -> int:
        return sum(feitos for feitos, _ in self.cobertura.values())

    @property
    def acordaos(self) -> int:
        return sum(total for _, total in self.cobertura.values())

    def texto(self) -> str:
        linhas = ["# Relatório de construção do índice canônico", ""]
        linhas.append("## Cobertura por tribunal")
        for tribunal in sorted(self.cobertura):
            feitos, total = self.cobertura[tribunal]
            linhas.append(f"- {tribunal}: {feitos}/{total}")
        linhas.append(f"- total de acórdãos: {self.acordaos_indexados}/{self.acordaos}")
        linhas.append(f"- súmulas: {self.sumulas} · dispositivos: {self.dispositivos}")
        linhas += ["", "## Chaves por registro"]
        for quantidade in sorted(self.chaves_por_registro):
            linhas.append(f"- {quantidade} chave(s): {self.chaves_por_registro[quantidade]} registros")
        linhas += ["", "## Colisões de chave"]
        linhas.append(f"- duplicatas do mesmo acórdão: {len(self.colisoes_duplicatas)} grupos")
        linhas.append(f"- fases recursais distintas: {len(self.colisoes_distintas)} grupos")
        for titulo, grupos in (("Duplicatas", self.colisoes_duplicatas),
                               ("Fases recursais distintas", self.colisoes_distintas)):
            linhas += ["", f"### {titulo}"]
            linhas += [f"- {chave}: {', '.join(docs)}" for chave, docs in grupos]
        linhas += ["", "## CNJ reprovados na validação"]
        linhas += [f"- {doc}: `{trecho}` ({motivo})" for doc, trecho, motivo in self.cnj_reprovados]
        linhas += ["", "## Divergências de âncora do TST"]
        linhas += [f"- {doc}: primeira ocorrência {chave} descartada" for doc, chave in self.ancoras_tst_divergentes]
        linhas += ["", "## Número encontrado só na janela estendida"]
        linhas += [f"- {doc}" for doc in self.janela_estendida]
        linhas += ["", "## Exceções curadas usadas"]
        linhas += [f"- {doc}: {chave} ({motivo})" for doc, chave, motivo in self.excecoes_usadas]
        linhas += ["", "## Cadeias de classe com resíduo na normalização"]
        linhas += [f"- {doc}: `{cadeia}` (sobrou: {sobra})" for doc, cadeia, sobra in self.cadeias_sem_normalizacao]
        return "\n".join(linhas) + "\n"


def _assinatura(texto: str) -> str:
    return re.sub(r"\s+", " ", texto[:TAMANHO_DA_ASSINATURA]).strip()


def _carregar_excecoes(caminho: Path | None) -> list[dict]:
    if caminho is None or not caminho.exists():
        return []
    with caminho.open("rb") as arquivo:
        return tomllib.load(arquivo).get("excecao", [])


class Indice:
    def __init__(self) -> None:
        self._por_chave: dict[str, list[int]] = defaultdict(list)
        self._sumulas: dict[ChaveSumula, int] = {}
        self._dispositivos: dict[tuple[ChaveDiploma, int | str], int] = {}
        self._registros: dict[int, Candidato] = {}
        self._assinaturas: dict[int, str] = {}
        self._cadeias_limpas: set[int] = set()
        # chave -> {id: id canônico}, só para quem tem duplicata; calculado na construção
        self._canonicos: dict[str, dict[int, int]] = {}
        self.relatorio = Relatorio()

    # ------------------------------------------------------------------ consultas

    def consultar_processo(self, identificador: str, tribunal: str | None = None) -> list[Candidato]:
        """Consulta exata pela chave numérica. Nunca faz casamento aproximado."""
        chave = chave_numerica(identificador)
        canonicos = self._canonicos.get(chave, {})
        resultado = []
        for id_ in self._por_chave.get(chave, []):
            candidato = self._registros[id_]
            if tribunal is not None and candidato.tribunal != tribunal:
                continue
            if id_ in canonicos:
                candidato = replace(candidato, duplicata=True, canonico=id_ == canonicos[id_])
            resultado.append(candidato)
        return resultado

    def _agrupar_duplicatas(self, ids: list[int]) -> dict[int, int]:
        """Duplicatas do mesmo acórdão entre os registros de uma chave: id -> id canônico.

        Dois registros do mesmo tribunal são o mesmo acórdão se têm cabeçalho idêntico
        ou cadeia de classe normalizada igual, não vazia e sem resíduo (DEC-019). Os dois
        critérios se combinam por fecho transitivo, e o canônico é o menor id (DEC-015).
        """
        pai = {id_: id_ for id_ in ids}

        def raiz(id_: int) -> int:
            while pai[id_] != id_:
                pai[id_] = pai[pai[id_]]
                id_ = pai[id_]
            return id_

        for a, b in combinations(ids, 2):
            ra, rb = self._registros[a], self._registros[b]
            if ra.tribunal != rb.tribunal:
                continue
            mesma_cadeia = (
                a in self._cadeias_limpas and b in self._cadeias_limpas
                and ra.cadeia_normalizada == rb.cadeia_normalizada
            )
            if mesma_cadeia or self._assinaturas[a] == self._assinaturas[b]:
                pai[raiz(a)] = raiz(b)
        grupos: dict[int, list[int]] = defaultdict(list)
        for id_ in ids:
            grupos[raiz(id_)].append(id_)
        return {id_: min(grupo) for grupo in grupos.values() if len(grupo) > 1 for id_ in grupo}

    def consultar_sumula(
        self, numero: int | str, tribunal: str | None = None, vinculante: bool = False
    ) -> list[Candidato]:
        alvo = int(so_digitos(str(numero)) or 0)
        return [
            self._registros[id_]
            for (trib, vinc, num), id_ in sorted(self._sumulas.items())
            if num == alvo and vinc == vinculante and tribunal in (None, trib)
        ]

    def consultar_dispositivo(self, diploma: str, artigo: str | int) -> list[Candidato]:
        chave_diploma = normalizar_diploma(diploma)
        numero = numero_do_artigo(artigo)
        letra = letra_do_artigo(artigo)
        if numero and letra:  # "896-A" é outro artigo, nunca o 896
            numero = f"{numero}{letra}"
        id_ = self._dispositivos.get((chave_diploma, numero)) if chave_diploma and numero else None
        return [self._registros[id_]] if id_ is not None else []

    # ------------------------------------------------------------------ inspeção

    def chaves_do_registro(self, id_: int) -> list[str]:
        return sorted(chave for chave, ids in self._por_chave.items() if id_ in ids)

    def serializar(self) -> bytes:
        """Forma canônica do índice, para o teste de determinismo."""
        conteudo = {
            "processos": {chave: ids for chave, ids in sorted(self._por_chave.items())},
            "sumulas": [[*chave, id_] for chave, id_ in sorted(self._sumulas.items())],
            "dispositivos": [[*diploma, artigo, id_]
                             for (diploma, artigo), id_ in sorted(
                                 self._dispositivos.items(),
                                 key=lambda item: (item[0][0], numero_do_artigo(str(item[0][1])), str(item[0][1])))],
            "registros": {str(id_): asdict(self._registros[id_]) for id_ in sorted(self._registros)},
        }
        return json.dumps(conteudo, ensure_ascii=False, sort_keys=True).encode("utf-8")


def construir_indice(
    caminho_base: Path | str, caminho_excecoes: Path | None = EXCECOES_PADRAO, estrito: bool = True
) -> Indice:
    """Indexa a base. `estrito` (desenvolvimento) aborta no primeiro registro que não indexa;
    sem ele (base desconhecida, avaliação final), o registro fica fora do índice, com aviso no
    stderr, e a execução segue: registro fora do índice vira `inventada`, nunca chave falsa."""

    def falhar(mensagem: str) -> None:
        if estrito:
            raise ErroDeConstrucao(mensagem)
        print(f"aviso: {mensagem}", file=sys.stderr)

    indice = Indice()
    relatorio = indice.relatorio
    excecoes = _carregar_excecoes(caminho_excecoes)
    excecoes_por_doc: dict[str, list[dict]] = defaultdict(list)
    for excecao in excecoes:
        excecoes_por_doc[excecao["documento_id"]].append(excecao)

    conexao = sqlite3.connect(f"file:{Path(caminho_base)}?mode=ro", uri=True)
    try:
        linhas = conexao.execute(
            "SELECT id, documento_id, natureza, tribunal, ano, relator, texto "
            "FROM documentos ORDER BY id"
        ).fetchall()
    finally:
        conexao.close()

    documentos_vistos = set()
    sem_chave: list[str] = []
    totais: Counter[str] = Counter()
    indexados: Counter[str] = Counter()
    quantidades: Counter[int] = Counter()

    for id_, documento_id, natureza, tribunal, ano, relator, texto in linhas:
        documentos_vistos.add(documento_id)
        base = Candidato(id_, documento_id, natureza, tribunal, ano, relator)

        if natureza == "sumula":
            chave_sumula = chave_de_sumula_da_base(texto)
            if chave_sumula is None:
                falhar(f"súmula sem chave reconhecível: {documento_id}")
                continue
            indice._sumulas[chave_sumula] = id_
            indice._registros[id_] = base
            continue
        if natureza == "dispositivo":
            chave_dispositivo = chave_de_dispositivo_da_base(texto)
            if chave_dispositivo is None:
                falhar(f"dispositivo sem chave reconhecível: {documento_id}")
                continue
            indice._dispositivos[chave_dispositivo] = id_
            indice._registros[id_] = base
            continue

        if tribunal not in EXTRATORES:
            falhar(f"acórdão de tribunal sem extrator ({tribunal}): {documento_id}")
            continue
        totais[tribunal] += 1
        extracao = EXTRATORES[tribunal](texto)
        chaves = list(dict.fromkeys(extracao.chaves))
        for excecao in excecoes_por_doc.get(documento_id, []):
            # a exceção vale para o registro conferido à mão, não para o `documento_id`:
            # numa base diferente o mesmo id pode ser outro processo, e chave falsa é pior que ausente
            if excecao["chave"] not in texto:
                falhar(f"exceção curada não confere com o texto de {documento_id}: {excecao['chave']}")
                continue
            chave = chave_numerica(excecao["chave"])
            if chave not in chaves:
                chaves.append(chave)
            relatorio.excecoes_usadas.append((documento_id, excecao["chave"], excecao["justificativa"]))
        for trecho, motivo in dict.fromkeys(extracao.reprovados):
            relatorio.cnj_reprovados.append((documento_id, trecho, motivo))
        for nota in extracao.notas:
            if nota.startswith("tst_ancora_divergente"):
                relatorio.ancoras_tst_divergentes.append((documento_id, nota.split("=", 1)[1]))
            elif nota == "janela_estendida":
                relatorio.janela_estendida.append(documento_id)

        tokens, residuo = normalizar_cadeia(extracao.cadeia)
        if residuo or not tokens:
            relatorio.cadeias_sem_normalizacao.append(
                (documento_id, extracao.cadeia or "", " ".join(residuo) or "sem token")
            )
        else:
            indice._cadeias_limpas.add(id_)
        indice._registros[id_] = replace(
            base, uf=extracao.uf, cadeia=extracao.cadeia, cadeia_normalizada=tokens
        )
        indice._assinaturas[id_] = _assinatura(texto)
        if not chaves:
            sem_chave.append(documento_id)
            continue
        indexados[tribunal] += 1
        quantidades[len(chaves)] += 1
        for chave in chaves:
            indice._por_chave[chave].append(id_)

    orfas = sorted(doc for doc in excecoes_por_doc if doc not in documentos_vistos)
    if orfas:
        falhar(f"exceção curada aponta para registro inexistente: {', '.join(orfas)}")
    if sem_chave:
        falhar(
            "acórdãos sem chave válida (corrija o extrator ou cure uma exceção): "
            + ", ".join(sorted(sem_chave))
        )

    relatorio.cobertura = {t: (indexados[t], totais[t]) for t in sorted(totais)}
    relatorio.chaves_por_registro = dict(sorted(quantidades.items()))
    relatorio.sumulas = len(indice._sumulas)
    relatorio.dispositivos = len(indice._dispositivos)
    for chave in sorted(indice._por_chave):
        ids = sorted(indice._por_chave[chave])
        indice._por_chave[chave] = ids
        if len(ids) < 2:
            continue
        documentos = [indice._registros[i].documento_id for i in ids]
        canonicos = indice._agrupar_duplicatas(ids)
        if canonicos:
            indice._canonicos[chave] = canonicos
        # registros efetivos: cada grupo de duplicatas conta uma vez, pelo canônico
        efetivos = [i for i in ids if canonicos.get(i, i) == i]
        if len(efetivos) == 1:
            relatorio.colisoes_duplicatas.append((chave, documentos))
        else:
            relatorio.colisoes_distintas.append((chave, documentos))
    indice._por_chave = dict(indice._por_chave)
    return indice

