"""Emite a submissão do Kaggle: documentos -> um JSON por documento -> `submission.csv`.

É o comando do bundle de reprodutibilidade (R-D05): roda com **biblioteca padrão**, sem
rede, sem chave e sem instalar nada. Medir o resultado com `kaggle_metric.py` é outro
comando (`scripts/gerar_submissao.py`), porque a métrica da organização usa pandas.

Antes de gravar o CSV, confere o que invalida uma submissão inteira (CHK-40 a CHK-46):
todo documento presente, nenhuma célula vazia, nenhum par de spans com IoU >= 0,5 no
mesmo documento, `real` sempre com `id_canonico` só de dígitos, offsets em codepoints
com 0 <= inicio < fim, `trecho` igual ao recorte do original e confiança em [0, 1].

Uso:
    python scripts/emitir.py [--txt txt] [--saida out] [--base desafio1_bracis.db]
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from itertools import combinations
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from verificador.indice import construir_indice  # noqa: E402
from verificador.verificar import Citacao, verificar_documento  # noqa: E402


class ErroDeEmissao(RuntimeError):
    """A submissão não pôde ser gerada; a mensagem nomeia o documento."""


def _iou(a: Citacao, b: Citacao) -> float:
    intersecao = max(0, min(a.fim, b.fim) - max(a.inicio, b.inicio))
    return intersecao / ((a.fim - a.inicio) + (b.fim - b.inicio) - intersecao)


def conferir(documento_id: str, texto: str, citacoes: list[Citacao]) -> None:
    """CHK-44, CHK-43, CHK-45 e CHK-42: o que a métrica rejeita, citação a citação."""
    for citacao in citacoes:
        onde = f"{documento_id}: {citacao.trecho[:40]!r}"
        if not 0 <= citacao.inicio < citacao.fim <= len(texto):
            raise ErroDeEmissao(f"{onde}: span inválido ({citacao.inicio}, {citacao.fim})")
        if citacao.trecho != texto[citacao.inicio:citacao.fim]:
            raise ErroDeEmissao(f"{onde}: trecho diferente do recorte do original")
        if not 0.0 <= citacao.confianca <= 1.0:
            raise ErroDeEmissao(f"{onde}: confiança {citacao.confianca} fora de [0, 1]")
        tem_id = citacao.id_canonico is not None
        if tem_id != (citacao.classificacao == "real"):
            raise ErroDeEmissao(f"{onde}: id_canonico e classe {citacao.classificacao} não combinam")
        if tem_id and not str(citacao.id_canonico).isdigit():
            raise ErroDeEmissao(f"{onde}: id_canonico deve ser só dígitos")
    for a, b in combinations(citacoes, 2):
        if _iou(a, b) >= 0.5:
            raise ErroDeEmissao(f"{documento_id}: spans sobrepostos {a.trecho[:30]!r} e {b.trecho[:30]!r}")


def _tolerar(documento_id: str, texto: str, citacoes: list[Citacao]) -> list[Citacao]:
    """Modo da avaliação final: em vez de derrubar a submissão inteira, descarta a citação
    que a métrica rejeitaria e, entre spans sobrepostos, fica com o de maior confiança."""
    validas = []
    for citacao in citacoes:
        try:
            conferir(documento_id, texto, [citacao])
        except ErroDeEmissao as erro:
            print(f"aviso: citação descartada, {erro}", file=sys.stderr)
            continue
        validas.append(citacao)
    mantidas: list[Citacao] = []
    for citacao in sorted(validas, key=lambda c: (-c.confianca, c.inicio, c.fim)):
        if all(_iou(citacao, outra) < 0.5 for outra in mantidas):
            mantidas.append(citacao)
        else:
            print(f"aviso: {documento_id}: span sobreposto descartado {citacao.trecho[:30]!r}", file=sys.stderr)
    return sorted(mantidas, key=lambda c: (c.inicio, c.fim))


def _como_json(documento_id: str, citacoes: list[Citacao]) -> dict:
    return {
        "documento_id": documento_id,
        "citacoes": [
            {
                "inicio": c.inicio,
                "fim": c.fim,
                "trecho": c.trecho,
                "tipo": c.tipo,
                "classificacao": c.classificacao,
                "resolucao": {"id_canonico": str(c.id_canonico)} if c.classificacao == "real" else None,
                "confianca": c.confianca,
            }
            for c in citacoes
        ],
    }


def arquivos_da_pasta(pasta_txt: Path) -> dict[str, Path]:
    """`documento_id` -> arquivo. A extensão vale em qualquer caixa (`.TXT`); se a pasta só tiver
    subpastas, os documentos são procurados dentro delas."""
    def documentos(caminhos):
        return {c.stem: c for c in sorted(caminhos) if c.is_file() and c.suffix.lower() == ".txt"}

    return documentos(pasta_txt.iterdir()) or documentos(pasta_txt.rglob("*"))


def documentos_esperados(pasta_txt: Path, sample: Path | None) -> list[str]:
    """Os `documento_id` do conjunto: os do `sample_submission.csv`, ou os `.txt` da pasta."""
    if sample and sample.exists():
        with sample.open(encoding="utf-8-sig", newline="") as arquivo:
            return [linha["documento_id"] for linha in csv.DictReader(arquivo)]
    return sorted(arquivos_da_pasta(pasta_txt))


def emitir(pasta_txt: Path, saida: Path, caminho_base: Path, sample: Path | None = None,
           conversor: Path | None = None, tolerante: bool = False) -> tuple[Path, int]:
    """Gera os JSONs e o `submission.csv`; devolve o caminho do CSV e o total de citações.

    `tolerante` é o modo da avaliação final, sobre base e documentos desconhecidos: problema num
    registro, numa citação ou num documento vira aviso no stderr e a submissão sai mesmo assim
    (documento que falha sai com `-`). Sem ele, qualquer problema aborta, como no desenvolvimento."""
    esperados = documentos_esperados(pasta_txt, sample)
    if not esperados:
        raise ErroDeEmissao(f"nenhum documento em {pasta_txt}")
    indice = construir_indice(caminho_base, estrito=not tolerante)
    arquivos = arquivos_da_pasta(pasta_txt)

    pasta_json = saida / "json"
    pasta_json.mkdir(parents=True, exist_ok=True)
    for antigo in pasta_json.glob("*.json"):
        antigo.unlink()

    total = 0
    for documento_id in esperados:
        caminho = arquivos.get(documento_id, pasta_txt / f"{documento_id}.txt")
        if not caminho.exists():  # CHK-40: linha faltando derruba a submissão inteira
            raise ErroDeEmissao(f"falta o documento {caminho.name} em {pasta_txt}")
        # sem tradução de fim de linha: os offsets valem sobre o texto como distribuído
        if tolerante:
            try:
                texto = caminho.read_bytes().decode("utf-8")
                citacoes = _tolerar(documento_id, texto, verificar_documento(texto, indice))
            except Exception as erro:  # noqa: BLE001 · um documento não derruba os outros
                print(f"aviso: {documento_id} sai sem citações ({type(erro).__name__}: {erro})", file=sys.stderr)
                citacoes = []
        else:
            texto = caminho.read_bytes().decode("utf-8")
            citacoes = verificar_documento(texto, indice)
            conferir(documento_id, texto, citacoes)
        total += len(citacoes)
        (pasta_json / f"{documento_id}.json").write_text(
            json.dumps(_como_json(documento_id, citacoes), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    destino = saida / "submission.csv"
    subprocess.run(
        [sys.executable, str(conversor or RAIZ / "json_to_submission.py"), str(pasta_json), str(destino)],
        check=True, stdout=subprocess.DEVNULL,
    )
    with destino.open(encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    if [l["documento_id"] for l in linhas] != esperados:  # CHK-40
        raise ErroDeEmissao("o CSV não tem exatamente os documentos do conjunto")
    if any(not l["citacoes"] for l in linhas):  # CHK-41: célula vazia, nunca
        raise ErroDeEmissao("o CSV tem célula vazia; documento sem citação usa '-'")
    return destino, total


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--txt", type=Path, default=RAIZ / "txt", help="pasta dos documentos")
    argumentos.add_argument("--saida", type=Path, default=RAIZ / "out", help="onde gravar JSONs e CSV")
    argumentos.add_argument("--base", type=Path, default=RAIZ / "desafio1_bracis.db", help="base canônica")
    argumentos.add_argument("--sample", type=Path, default=RAIZ / "sample_submission.csv",
                            help="lista de documentos do conjunto; sem ele, usa os .txt da pasta")
    argumentos.add_argument("--tolerante", action="store_true",
                            help="avaliação final: avisa e segue em vez de abortar (ver emitir)")
    opcoes = argumentos.parse_args()
    destino, total = emitir(opcoes.txt, opcoes.saida, opcoes.base, opcoes.sample, tolerante=opcoes.tolerante)
    print(f"{total} citações em {len(documentos_esperados(opcoes.txt, opcoes.sample))} documentos")
    print(f"pronto para enviar: {destino}")


if __name__ == "__main__":
    main()
