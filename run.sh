#!/bin/sh
# Ponto de entrada único da avaliação final:
#
#   bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>
#
# Lê todos os .txt da pasta, resolve as citações contra a base e grava o CSV no
# formato da submissão. Só biblioteca padrão do Python 3.12: sem rede, sem GPU,
# sem modelo. Os JSONs intermediários (um por documento) ficam ao lado do CSV,
# em <arquivo_saida>.json/.
#
# Roda em modo tolerante: um registro da base que não indexa, uma citação inválida ou
# um documento que falha viram aviso no stderr, e o CSV sai mesmo assim.
set -eu

if [ "$#" -ne 3 ]; then
    echo "uso: bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>" >&2
    exit 2
fi

DB=$1
TXT=$2
SAIDA=$3
RAIZ=$(cd "$(dirname "$0")" && pwd)
PYTHON=${PYTHON:-python3}

"$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' || {
    echo "precisa de Python 3.11 ou mais novo (testado no 3.12); defina PYTHON=..." >&2
    exit 2
}

TRABALHO="$SAIDA.json"
mkdir -p "$TRABALHO" "$(dirname "$SAIDA")"

# Sem sample: o conjunto é o dos .txt da pasta, em ordem de nome.
# O caminho inexistente desliga a leitura do sample_submission.csv padrão.
PYTHONHASHSEED=0 "$PYTHON" "$RAIZ/scripts/emitir.py" \
    --base "$DB" --txt "$TXT" --saida "$TRABALHO" \
    --sample "$TRABALHO/sem-sample.csv" --tolerante

mv "$TRABALHO/submission.csv" "$SAIDA"
echo "saída: $SAIDA"
