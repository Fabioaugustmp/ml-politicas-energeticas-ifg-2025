# Projeto Goiás Renovável - ml-politicas-energeticas-ifg-2025
PROJETO — MÓDULO 2: Machine Learning para Políticas Públicas Energéticas - POS IA IFG 2025/1

## Arquitetura do Pipeline de Dados e MLOps

Aqui está o fluxo de trabalho automatizado para o projeto de potencial energético, desde a extração de dados até o treinamento do modelo.

```mermaid
graph TD
    subgraph "Fontes de Dados Externas"
        A["Dados em Arquivos<br/>- ANEEL (Usinas CSV)<br/>- IBGE (Shapefiles)<br/>- INMET (CSVs Meteorológicos)<br/>- ONS (Shapefiles de Rede)<br/>- IMB (PIB CSV)"]
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


# Activate DBT env


```bash
 conda activate ml-dbt
```

conda deactivate
Overview
========

Welcome to Astronomer! This project was generated after you ran 'astro dev init' using the Astronomer CLI. This readme describes the contents of the project, as well as how to run Apache Airflow on your local machine.

Project Contents
================

Your Astro project contains the following files and folders:

- dags: This folder contains the Python files for your Airflow DAGs. By default, this directory includes one example DAG:
    - `example_astronauts`: This DAG shows a simple ETL pipeline example that queries the list of astronauts currently in space from the Open Notify API and prints a statement for each astronaut. The DAG uses the TaskFlow API to define tasks in Python, and dynamic task mapping to dynamically print a statement for each astronaut. For more on how this DAG works, see our [Getting started tutorial](https://www.astronomer.io/docs/learn/get-started-with-airflow).
- Dockerfile: This file contains a versioned Astro Runtime Docker image that provides a differentiated Airflow experience. If you want to execute other commands or overrides at runtime, specify them here.
- include: This folder contains any additional files that you want to include as part of your project. It is empty by default.
- packages.txt: Install OS-level packages needed for your project by adding them to this file. It is empty by default.
- requirements.txt: Install Python packages needed for your project by adding them to this file. It is empty by default.
- plugins: Add custom or community plugins for your project to this file. It is empty by default.
- airflow_settings.yaml: Use this local-only file to specify Airflow Connections, Variables, and Pools instead of entering them in the Airflow UI as you develop DAGs in this project.

Deploy Your Project Locally
===========================

Start Airflow on your local machine by running 'astro dev start'.

This command will spin up five Docker containers on your machine, each for a different Airflow component:

- Postgres: Airflow's Metadata Database
- Scheduler: The Airflow component responsible for monitoring and triggering tasks
- DAG Processor: The Airflow component responsible for parsing DAGs
- API Server: The Airflow component responsible for serving the Airflow UI and API
- Triggerer: The Airflow component responsible for triggering deferred tasks

When all five containers are ready the command will open the browser to the Airflow UI at http://localhost:8080/. You should also be able to access your Postgres Database at 'localhost:5432/postgres' with username 'postgres' and password 'postgres'.

Note: If you already have either of the above ports allocated, you can either [stop your existing Docker containers or change the port](https://www.astronomer.io/docs/astro/cli/troubleshoot-locally#ports-are-not-available-for-my-local-airflow-webserver).

Deploy Your Project to Astronomer
=================================

If you have an Astronomer account, pushing code to a Deployment on Astronomer is simple. For deploying instructions, refer to Astronomer documentation: https://www.astronomer.io/docs/astro/deploy-code/

Contact
=======

The Astronomer CLI is maintained with love by the Astronomer team. To report a bug or suggest a change, reach out to our support.
