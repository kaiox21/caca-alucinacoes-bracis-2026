# Desafio Caça-Alucinação · Jusbrasil × BRACIS 2026

Verificação de citações jurídicas em pareceres gerados por IA: para cada documento, localizar as citações de jurisprudência e de lei e classificar cada uma como `real` (com o `id_canonico`), `inventada` ou `incompleta`.

A solução é **determinística e sem modelo**: regras e um índice da base congelada, só com a biblioteca padrão do Python. Não há rede, chave de API, GPU nem peso de modelo em nenhuma etapa da execução.

| | |
|---|---|
| Score no conjunto de desenvolvimento | **1,1000** (teto da métrica), macro-F1 1,000 nos dois níveis, τ 0 |
| Tempo de execução | menos de 1 segundo para os 26 documentos |
| Pico de memória | 263 MB (envelope permitido: 32 GB) |
| Dependências na execução | nenhuma além do Python 3.12 |

## Como executar (avaliação final)

Ponto de entrada único. Recebe o caminho do `.db`, a pasta com os `.txt` e o arquivo de saída, e grava o CSV no formato da submissão:

```bash
bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>
# exemplo
bash run.sh desafio1_bracis.db txt saida/submission.csv
```

Requisito: Python 3.12 (qualquer 3.11 ou mais novo serve), **nada instalado**. Se o `python3` da máquina for mais antigo, indique outro: `PYTHON=python3.12 bash run.sh ...`. O conjunto é o dos `.txt` da pasta, em ordem de nome; os JSONs intermediários, um por documento, ficam em `<arquivo_saida>.json/`.

Não há pré-processamento separado nem enriquecimento persistido do `.db`: o índice é construído em memória a partir da base no formato original, a cada execução (cerca de 0,5 s), dentro do próprio `run.sh`. A base é aberta só para leitura.

O `run.sh` roda em **modo tolerante**, porque a base e os documentos da avaliação são desconhecidos: um registro que não indexa fica fora do índice (uma citação a ele sai `inventada`, nunca com chave falsa), uma citação que a métrica rejeitaria é descartada, e um documento que falha sai com `-`. Cada caso vira um aviso no stderr, e o CSV sai mesmo assim. O `scripts/emitir.py` sem `--tolerante` mantém o modo estrito do desenvolvimento, em que qualquer um desses casos aborta.

### No contêiner

```bash
docker build -t verificador-bracis .
docker run --rm --network none \
  -v "$PWD:/dados:ro" -v "$PWD/saida:/saida" \
  verificador-bracis /dados/desafio1_bracis.db /dados/txt /saida/submission.csv
```

A imagem é `python:3.12-slim` e **não instala nada**: carrega o código e roda `run.sh` com os mesmos três argumentos. Não usa GPU nem rede (roda com `--network none`). Os dados entram como volume só de leitura e nunca são copiados para dentro da imagem.

### Reproduzir a submissão do Kaggle

Os dados da competição não estão neste repositório. Baixe na aba Data e ponha na raiz `desafio1_bracis.db`, `txt/` e `sample_submission.csv`. O conversor oficial `json_to_submission.py` já está versionado aqui, sem alteração. Então:

```bash
python scripts/emitir.py          # out/submission.csv, na ordem do sample_submission.csv
```

### Determinismo

Medido em 22/09/2026 e de novo em 01/10/2026 (cópia limpa do repositório, `run.sh` local e no contêiner sem rede): cinco execuções (duas na máquina, duas no contêiner e a do repositório) produziram `submission.csv` idêntico byte a byte, com sha256

```
f89bcf50fd0142b38df90467e6c77f37d558d03c504a0a42e5607dd7fe85bd1a
```

Não há amostragem, temperatura nem semente a fixar: não existe modelo. O `run.sh` ordena os documentos pelo nome do `.txt` (o `scripts/emitir.py` com sample, pela ordem do `sample_submission.csv`) e as citações pelo início do span.

## Como a solução funciona

```
txt/  ─►  normalização 1:1  ─►  extração por família  ─►  índice da base  ─►  resolução  ─►  JSON  ─►  submission.csv
```

| módulo | papel |
|---|---|
| `verificador/normalizacao.py` | troca só caracteres de superfície (espaços Unicode, `°`, travessões), 1 caractere por 1, para que os offsets continuem valendo em codepoints sobre o texto como distribuído |
| `verificador/extracao/` | acha e delimita as citações: processo ancorado no **número**, com a cadeia de classe crescendo para a esquerda pelo vocabulário levantado dos cabeçalhos da base; e lei, súmula, tema e referência descritiva |
| `verificador/indice/` | índice da base congelada: número do próprio processo de cada acórdão, validação do CNJ, súmulas e dispositivos. Consulta exata, sem casamento aproximado de dígitos |
| `verificador/resolucao.py` | decide a classe: 0 candidatos é `inventada`; 1 registro é `real`; 2 ou mais só resolvem se a cadeia de classe citada for igual à de exatamente um deles, senão `incompleta` |
| `verificador/verificar.py` | junta tudo: `verificar_documento(texto, indice)` |
| `run.sh` | ponto de entrada único da avaliação: `<db> <pasta_txt> <arquivo_saida>` |
| `scripts/emitir.py` | JSONs, conversor oficial e as conferências que invalidam uma submissão |

Duas invariantes que explicam o resto: **mundo fechado** (`real` significa "resolve a um registro da base", e nenhuma consulta sai dela) e **sem casamento aproximado de dígitos** (o ruído se corrige na normalização; a consulta é exata, porque marcar uma citação inventada como real é o erro mais caro da métrica).

## Modelo, licença e ambiente

- **Não há modelo**, nem fine-tuning, nem pesos: os itens de referência de modelo do bundle não se aplicam.
- Execução: Python 3.12, biblioteca padrão, CPU. `Dockerfile` na raiz. Sem GPU, sem internet, sem API externa.
- Licença do código: MIT (`LICENSE`).

## Ferramentas

O desenvolvimento usou o Claude Code como assistente de programação. A abordagem, as decisões de método e a validação são da equipe.

## Sobre este repositório

É a versão final submetida, só com o que a execução precisa. O desenvolvimento (suíte de testes, scripts de medição, gerador sintético e o registro de decisões e experimentos citados nos comentários do código como `DEC-…`, `EXP-…`, `CHK-…`) fica no repositório de trabalho da equipe, fora daqui porque contém trechos do gabarito de desenvolvimento, que é dado da competição.
