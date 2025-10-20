# Projeto Goiás Renovável — ml-politicas-energeticas-ifg-2025

## Visão geral

Este repositório contém o código, DAGs, notebooks e utilitários para o pipeline de ingestão, transformação (dbt) e treinamento de modelos do projeto "Goiás Renovável" — Módulo 2 do curso POS IA IFG (2025/1). O fluxo geral é: ingestão de dados públicos → armazenamento em S3 → carga no DWH → transformações com dbt → treinamento e registro de modelos.

## Modelo de Análise

[Análise Potencial](http://20.206.241.65:8501/)

[![Goiás](images/goias-data.png)](http://20.206.241.65:8501/)
## Arquitetura (mermaid)

```mermaid
graph TD
    subgraph "Fontes de Dados Externas"
        A["Dados em Arquivos<br/>- ANEEL (Usinas CSV)<br/>- IBGE (Shapefiles)<br/>- INMET (CSVs Meteorológicos)<br/>- ONS (Shapefiles de Rede)<br/>- IMB (PIB CSV)<br/>- BDE GOIÁS (Banco de Dados Estatísticos)"]
    end

    subgraph "Orquestração e Execução"
        B("Apache Airflow<br/>Orquestrador Central")
    end

    subgraph "Camada de Armazenamento (Cloud - AWS S3)"
        S3_RAW["S3 Data Lake<br/>(Dados Brutos)"]
        S3_MODELS["S3 Model Registry<br/>(Modelos Treinados .pkl)"]
    end

    subgraph "Data Warehouse (Processamento e Análise)"
        CH("SnowFlake")
        CH_RAW["Tabelas Brutas<br/>raw_aneel, raw_inmet..."]
        CH_MART["Tabela Analítica<br/>mart_microrregiao_potencial"]
        CH --- CH_RAW & CH_MART
    end
    
    subgraph "Lógica de Negócio e ML"
        C["Script de Ingestão<br/>(Python/GeoPandas)"]
        D["dbt (data build tool)<br/>(Transformação SQL)"]
        E["Script de Treinamento ML<br/>(Python/Scikit-learn/XGBoost)"]
    end

    subgraph "Consumo dos Resultados"
        F["Dashboards & Análises<br/>(Power BI, Metabase, etc.)"]
        G["API de Inferência<br/>(Servindo o modelo)"]
    end

    %% FLUXO DO PIPELINE
    B -->|1. Dispara Script| C
    A -->|2. Lê arquivos| C
    C -->|3. Salva dados brutos| S3_RAW
    S3_RAW -->|4. Carrega no DWH| CH_RAW

    B -->|5. Dispara Transformação| D
    CH_RAW -->|6. dbt lê dados brutos| D
    D -->|7. dbt cria tabela analítica| CH_MART

    B -->|8. Dispara Treinamento| E
    CH_MART -->|9. Lê dados de treino| E
    E -->|10. Salva modelo treinado| S3_MODELS

    CH_MART -->|Análise| F
    S3_MODELS -->|Deploy| G
```

## Estrutura do repositório (resumo)

- `dags/` — Airflow DAGs de ingestão, ETL/ELT e tarefas operacionais.
- `dbt/` e `include/dbt_inmet_s3_ingestion/` — projetos dbt para transformação de dados.
- `scripts/` — utilitários (upload S3, manipulação de nomes, helpers).
- `drive/` — amostras de dados e artefatos (não versionar dados sensíveis).
- Notebooks na raiz (`*.ipynb`) — EDA e treinamento.
- `requirements.txt` — dependências Python (existem `requirements.txt` também nos subprojetos dbt).
- `Dockerfile`, `compose/` — configuração de runtime para Airflow.

> Observação: há lógica auxiliar em `dags/` e `scripts/`. Recomenda-se consolidar em `src/` para melhor testabilidade e reutilização.

---

## Pré-requisitos

- Python 3.10+ para execução local de scripts.
- Docker e Docker Compose para orquestrar Airflow localmente.
- Credenciais AWS (para acesso ao S3) e credenciais Snowflake (para carga/transformação), configuradas via Airflow Connections ou variáveis de ambiente.

---

## Setup rápido (local)

1) Criar ambiente Python e instalar dependências:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Configurar conexões e variáveis (Airflow):
- Criar conexões `aws_default` e `snowflake_default` via UI do Airflow (Recom.) ou via CLI.
- Preferir Secret Backends ou AWS Secrets Manager para credenciais.

---

## Executando com Docker Compose (Airflow)

Suba um cluster simples (webserver em http://localhost:8081):

```bash
docker compose -f compose/airflow.yml up --build -d
```

Primeiro acesso e checagens úteis:

```bash
# Ver logs do webserver
docker compose -f compose/airflow.yml logs -f airflow-webserver

# Listar DAGs disponíveis
docker compose -f compose/airflow.yml exec airflow-webserver airflow dags list

# (Exemplo) disparar uma DAG pelo ID
docker compose -f compose/airflow.yml exec airflow-webserver \
  airflow dags trigger <SEU_DAG_ID>
```

Outros serviços:
- Flower: http://localhost:5555
- Redis: 6379 (local)

Para encerrar:

```bash
docker compose -f compose/airflow.yml down -v
```

---

## Executando dbt

Execute dbt no projeto de ingestão INMET (ajuste o profile conforme seu ambiente):

```bash
cd include/dbt_inmet_s3_ingestion
dbt debug --profiles-dir . --project-dir .
dbt run   --profiles-dir . --project-dir .
dbt test  --profiles-dir . --project-dir .
```

---

## Scripts úteis

Upload de arquivos listados em `drive/files.txt` para S3 (vide `scripts/README.md` para detalhes):

```bash
# Dry-run (somente verificar caminhos)
python3 scripts/upload_files_to_s3.py --dry-run --prefix drive

# Upload (defina bucket e prefix conforme necessário)
python3 scripts/upload_files_to_s3.py --bucket <SEU_BUCKET> --prefix drive --upload-metrics
```

Outros scripts:
- `scripts/list_s3.py`, `scripts/rename_s3_files.sh` — utilitários diversos. Use `-h` para ajuda quando disponível.

---

## Notebooks

- `exploratory_data_analysis.ipynb` — EDA básica.
- `CC_ML_TRAINING_MODEL.ipynb` — treinamento de modelo (Colab-ready).
- [`CC_ML_TRAINING_MODEL.ipynb`](https://colab.research.google.com/drive/1jHJq_-zXsGDkPS3lfudIrirHqU68i9jX?usp=sharing)  — treinamento de modelo (Colab Execution).

Recomendação: use um kernel Python do seu virtualenv (`.venv`) e garanta que as dependências estejam instaladas.

---

## DAGs (descrição breve)

- `dbt_snowflake_dag.py` — DAG de debugging: executa `dbt debug` para validar configuração do dbt.
- `dbt_inmet_dag.py` — Executa modelos dbt por ano; seleciona `dados_meteriologicos_inmet` via `--select` lendo CSVs INMET no S3.
- `inmet_data_to_snowflake_dbt_etl.py` — Pipeline ELT principal: cria file formats/staging, lista S3 e executa `COPY INTO` para staging.
- `read_data_then_sent.py` — Leitura de S3 com pandas e carga via `write_pandas` no Snowflake.
- `inmet_csv_to_s3*` — Variações de download/envelope para S3 (streaming, in-memory, paralelização).
- `inmet_data_download*.py` — Download e preparação por ano.
- `inmet_data_cleaner.py`, `clean_s3_keep_go_csv.py` — Limpeza e retenção seletiva no bucket S3.



---


## 👥 Equipe

| Foto | Nome |  GitHub |
|:---:|:---|:---|
| ![Fabioaugustmp](https://github.com/Fabioaugustmp.png?size=50) | **Fabio A. M. Paula |[@Fabioaugustmp](https://github.com/Fabioaugustmp) |
| <img src="https://github.com/dr-marcelocarvalho.png" width="50"> | **Marcelo R. Carvalho**  | [@dr-marcelocarvalho](https://github.com/dr-marcelocarvalho)|
| ![ficheles](https://github.com/ficheles.png?size=50) | **Rafael F. Costa**  | [@Ficheles](https://github.com/ficheles) |
| ![NascimentoRaony](https://github.com/NascimentoRaony.png?size=50) | **Raony N. Nogueira**  | [@NascimentoRaony](https://github.com/NascimentoRaony) |

---
