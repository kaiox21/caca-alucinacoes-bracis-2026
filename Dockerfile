# Bundle de reprodutibilidade (R-D05): a emissão roda só com a biblioteca padrão,
# então a imagem não instala nada. Sem pip, sem lockfile a resolver, sem rede além
# do download da imagem base.
#
# Os dados da competição não entram na imagem (DEC-009): vêm como volume só de leitura.
#
# O contêiner recebe os mesmos três argumentos do run.sh (db, pasta dos .txt, CSV de saída):
#
#   docker build -t verificador-bracis .
#   docker run --rm -v "$PWD:/dados:ro" -v "$PWD/out:/saida" verificador-bracis \
#     /dados/desafio1_bracis.db /dados/txt /saida/submission.csv
FROM python:3.12-slim

WORKDIR /app
COPY verificador/ /app/verificador/
COPY scripts/emitir.py /app/scripts/emitir.py
COPY json_to_submission.py /app/json_to_submission.py
COPY run.sh /app/run.sh

ENV PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["sh", "/app/run.sh"]
CMD ["/dados/desafio1_bracis.db", "/dados/txt", "/saida/submission.csv"]
