# Caça-Alucinações · Jusbrasil × BRACIS 2026

**Equipe "é a bahia"** · Kaio Xavier Silva, Rafael Brito Valadares, Pedro Barreto Palheta de Oliveira e Vitor De Pádua Moreira Justo

Verificação de citações jurídicas em documentos gerados por IA: para cada documento, localizar as citações de jurisprudência e de lei e classificar cada uma como `real` (com o `id_canonico`), `inventada` ou `incompleta`.

A solução é **determinística e sem modelo**: regras de extração e um índice construído a partir da base, só com a biblioteca padrão do Python. Não há rede, chave de API, GPU nem peso de modelo em nenhuma etapa.

| | |
|---|---|
| Score no conjunto de desenvolvimento | **1,1000** (teto da métrica): macro-F1 1,000 nos dois níveis, τ 0 |
| Tempo de execução | menos de 1 segundo para os 26 documentos, incluída a construção do índice |
| Memória | menos de 300 MB |
| Hardware | CPU. Não usa GPU |
| Dependências na execução | nenhuma além do Python 3.12 |

## Como executar

Ponto de entrada único. Recebe o caminho do `.db`, a pasta com os `.txt` e o arquivo de saída:

```bash
bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>

# exemplo
bash run.sh desafio1_bracis.db txt saida/submission.csv
```

Requisito: Python 3.12 (3.11 ou mais novo serve), **sem instalar nada**. Se o `python3` da máquina for mais antigo, indique outro: `PYTHON=python3.12 bash run.sh ...`.

### No contêiner

```bash
docker build -t verificador-bracis .
docker run --rm --network none \
  -v "$PWD:/dados:ro" -v "$PWD/saida:/saida" \
  verificador-bracis /dados/desafio1_bracis.db /dados/txt /saida/submission.csv
```

A imagem é `python:3.12-slim` e **não instala nada**: carrega o código e roda o `run.sh` com os mesmos três argumentos. Os dados entram como volume só de leitura e nunca são copiados para dentro da imagem. O exemplo roda com `--network none` para deixar explícito que a execução é offline.

### O que sai

O arquivo de saída é o CSV no formato da submissão, uma linha por documento, na ordem do nome do arquivo:

```csv
documento_id,citacoes
doc_a,"120,137,real,1234567890,1.0000|310,352,inventada,-,1.0000|498,561,incompleta,-,1.0000"
doc_b,-
```

Cada citação é `inicio,fim,classe,id_canonico,confianca`, com offsets em codepoints Unicode sobre o texto como distribuído. Documento sem citação sai com `-`. Ao lado do CSV fica a pasta `<arquivo_saida>.json/`, com um JSON por documento no contrato de saída (inclui o `trecho` e o `tipo`), convertido pelo `json_to_submission.py` oficial, sem alteração.

O `documento_id` é o nome do arquivo sem a extensão. A extensão vale em qualquer caixa (`.txt`, `.TXT`), e, se a pasta só tiver subpastas, os documentos são procurados dentro delas.

### Conformidade com as regras de execução

| Regra | Como é atendida |
|---|---|
| GPU de até 24 GB de VRAM | não usa GPU; roda em CPU com menos de 300 MB de RAM |
| Offline | nenhum acesso à rede no código; o contêiner roda com `--network none` |
| Máquina limpa | sem caminho absoluto, sem passo manual, sem arquivo fora do repositório |
| Pesos de modelo | não se aplica: não há modelo |
| Enriquecimento do `.db` | não há etapa separada: o índice é construído em memória a cada execução, a partir do `.db` no formato original, dentro do próprio `run.sh`. A base é aberta só para leitura |
| Determinismo | não há amostragem nem semente; duas execuções dão o mesmo arquivo, byte a byte |
| Disco | o repositório tem menos de 1 MB |

### Base e documentos desconhecidos

O `run.sh` roda em **modo tolerante**, porque a base e os documentos da avaliação são outros:

- um registro da base que não indexa fica fora do índice (uma citação a ele sai `inventada`, nunca com chave falsa);
- uma citação que a métrica rejeitaria é descartada;
- um documento que falha sai com `-`, sem derrubar os outros.

Cada caso vira um aviso no stderr, e o CSV sai mesmo assim. No conjunto de desenvolvimento não há nenhum aviso.

## Abordagem

```
.txt ─► normalização 1:1 ─► extração por família ─► índice da base ─► resolução ─► JSON ─► CSV
```

Duas invariantes explicam o resto:

- **Mundo fechado.** `real` significa "resolve a um registro da base", e não "existe no mundo". Nenhuma consulta sai da base, e o que o código sabe de Direito é só nomenclatura (siglas de classe, apelidos de diploma). Quem decide é a base.
- **Sem casamento aproximado de dígitos.** As citações inventadas são vizinhas das reais (um dígito de diferença), e marcar uma inventada como `real` é o único erro com penalidade extra na métrica. O ruído é desfeito na leitura do número; a consulta é sempre exata.

### 1. Normalização que preserva offsets

Só caracteres de superfície mudam (espaços Unicode, `°` usado como ordinal, travessões, `\r`), e sempre 1 caractere por 1. A posição `i` do texto normalizado é a posição `i` do original, então todo span vale em codepoints sobre o texto como distribuído, sem mapa de offsets.

### 2. Extração por família

| Família | Como é achada |
|---|---|
| Processo | A âncora é o **número** (sequencial ou CNJ, com o ruído de formatação tolerado). A partir dele, a cadeia de classe cresce para a esquerda enquanto as palavras pertencem ao vocabulário de classes (`AgInt no AREsp`, `Embargos de Declaração no Recurso Especial`). Sem classe, o número não é citação: é o que afasta autos do próprio documento, protocolo, OAB, folhas e valores |
| Lei | Artigo + complemento (`caput`, inciso, parágrafo, alínea) + diploma, por número (`Lei nº 8.078/1990`), por nome (`Código Civil`) ou por sigla (`CPC`) |
| Súmula | Palavra-chave + número + tribunal, por sigla ou por extenso; `Vinculante` faz parte da chave |
| Descritiva | Tribunal ou classe + ano + relator, sem número (`julgado do STJ proferido em 2022 pela relatoria de …`) |

Candidatos que se sobrepõem são resolvidos num passo só, e os spans emitidos nunca têm interseção.

### 3. Índice da base

O número do processo não é coluna da base: está dentro do texto de cada acórdão, em posição e formato que mudam por tribunal. Um extrator por tribunal acha o número do **próprio** processo no cabeçalho, sem confundi-lo com os precedentes citados na ementa, e todo CNJ passa pela validação do dígito verificador antes de virar chave. A regra é que chave falsa é pior que chave ausente. Súmulas são indexadas por (tribunal, vinculante, número), e dispositivos por (diploma, artigo), com o diploma reduzido a tipo e número (o CPC é a `Lei nº 13.105`).

### 4. Resolução

| Situação | Classe |
|---|---|
| Nenhum registro com o número citado | `inventada` |
| Exatamente um registro | `real`, com o `id` dele |
| Dois ou mais registros com o mesmo número (fases recursais distintas) | `real` só se a cadeia de classe citada for **igual** à de exatamente um deles; senão `incompleta` |
| Referência descritiva, sem número | `incompleta`, sempre |
| Súmula ou dispositivo | `real` se a chave está na base; senão `inventada` |

A confiança é fixa por regra: 1,0 onde a base decide, 0,5 na única regra que declara não saber (colisão de número sem desempate).

### Exemplos

Supondo uma base que tenha o REsp 1.234.567, a Súmula 7 do STJ e o art. 5º da Constituição:

| Trecho no documento | Resultado |
|---|---|
| `REsp nº 1.234.567/SP` | `real`: o número resolve a um registro |
| `REsp nº 1.234.568/SP` | `inventada`: um dígito de diferença não aproxima |
| `R.Esp. 1 234 567 (SP)` | `real`: abreviação, espaço no número e separador de UF são ruído de superfície |
| `art. 5º, caput, da Constituição Federal` | `real` |
| `art. 5º-A da Constituição Federal` | `inventada`: artigo com letra é outro artigo |
| `Súmula 7 do Supremo Tribunal Federal` | `inventada`: a Súmula 7 da base é a do STJ |
| `julgado do STJ proferido em 2022 pela relatoria de Fulano de Tal` | `incompleta`: não há identificador que resolva |

### Ruído tratado

| Ruído | Onde é desfeito |
|---|---|
| Variação de abreviação (`REsp`, `R.Esp.`, `Recurso Especial`) | vocabulário de classes: sigla e nome por extenso viram o mesmo token |
| Formatação do número (`1.741.784`, `1741784`, `1.741. 784`) | leitura do número |
| Separador de UF (`/PR`, `- PR`, `(PR)`, por extenso) | extração do processo |
| Confusão de OCR em dígito (`0↔O`, `1↔l`, `5↔S`) | só dentro do número, colada a dígito; no resto do texto `art. 5o` continua `5o` |
| Confusão de OCR em letra (`5úmula`, `Fedcral`, `m↔rn`) | só nas palavras que a extração espera naquela posição |
| Quebra de linha no meio do identificador | leitura do número, da cadeia de classe e do nome do relator |
| Espaço não separável, `°`, travessões | normalização |

## Validação

O conjunto de desenvolvimento chegou ao teto e deixou de distinguir versões, então a validação passou a usar medidas que a equipe construiu a partir da base:

- **Ida e volta pela base:** cada acórdão é citado pelo próprio cabeçalho e tem de resolver ao próprio registro.
- **Gerador sintético:** documentos com gabarito conhecido, com o ruído documentado pela organização; metade das operações de ruído fica reservada e só entra na checagem final. Nos conjuntos padrão e reservado, mais de 8 mil citações com score 1,1000.
- **Conjunto adversarial:** formas fora do escopo, de propósito. Em 8.442 citações, 99,67% de acerto e nenhuma citação inventada marcada como `real`.
- **Base simulada:** uma base montada do zero, com classes, súmulas e dispositivos que a de desenvolvimento não tem, para medir o que vale fora dos registros conhecidos.
- **Estresse:** o verificador sobre os textos da própria base (documentos de até 127 mil caracteres) e sobre documentos com mutações aleatórias, sem exceção nem travamento.

A suíte tem 350 testes. Ela e os scripts de medição ficam no repositório de trabalho da equipe (ver o fim desta página).

## Limitações conhecidas

- **Classe em minúscula em número com mais de um registro.** A classe em minúscula delimita o span, mas não desempata; a citação sai `incompleta`. É a escolha conservadora.
- **Número de um ou dois dígitos sem marcador e sem UF** (`Rcl 87`) não é extraído: aceitar abriria falso positivo em texto corrido.
- **Tribunais fora de STF, STJ, TST, TSE e STM** não têm extrator: os registros ficam fora do índice, com aviso.
- **Tema** (repercussão geral, repetitivo) sai sempre `inventada`, porque a base não tem registro de tema.
- **Listas fechadas.** O vocabulário de classes e os apelidos de diploma cobrem os cinco tribunais além da base de desenvolvimento, mas continuam sendo listas: classe ou apelido fora delas não é reconhecido.

## Estrutura do repositório

| Caminho | Papel |
|---|---|
| `run.sh` | ponto de entrada da avaliação: `<db> <pasta_txt> <arquivo_saida>` |
| `Dockerfile` | ambiente: `python:3.12-slim`, sem instalar nada |
| `scripts/emitir.py` | gera os JSONs, chama o conversor oficial e confere o que invalida uma submissão |
| `json_to_submission.py` | conversor oficial da organização, sem alteração |
| `verificador/verificar.py` | `verificar_documento(texto, indice)`: junta as etapas |
| `verificador/normalizacao.py` | normalização 1 para 1 |
| `verificador/extracao/` | uma família por arquivo (`processo.py`, `lei.py`, `sumula_tema.py`, `descritiva.py`), leitura de números e resolução de conflitos de span |
| `verificador/cadeias.py` | vocabulário de classes processuais: sigla ↔ nome por extenso |
| `verificador/indice/` | extratores por tribunal, validação do CNJ, chaves de súmula e dispositivo, construção do índice |
| `verificador/resolucao.py` | regra de decisão para processo |

## Determinismo

Não há amostragem, temperatura nem semente a fixar. Sobre o conjunto de desenvolvimento, as execuções na máquina e no contêiner, a partir de um clone limpo, produzem o mesmo CSV, byte a byte, com sha256

```
f89bcf50fd0142b38df90467e6c77f37d558d03c504a0a42e5607dd7fe85bd1a
```

Para reproduzir a submissão do Kaggle na ordem do `sample_submission.csv`, com os dados da competição na raiz: `python scripts/emitir.py` grava `out/submission.csv`. Esse comando roda em modo estrito, em que qualquer problema aborta; é o modo do desenvolvimento.

## Licença e ferramentas

- Código sob licença MIT (`LICENSE`).
- O desenvolvimento usou o Claude Code como assistente de programação. A abordagem, as decisões de método e a validação são da equipe.

## Sobre este repositório

É a versão final submetida, só com o que a execução precisa. Os dados da competição não estão aqui. O desenvolvimento (suíte de testes, scripts de medição, gerador sintético e o registro de decisões e experimentos, citados nos comentários do código como `DEC-…`, `EXP-…` e `CHK-…`) fica no repositório de trabalho da equipe, que não é público porque contém trechos do gabarito de desenvolvimento.
