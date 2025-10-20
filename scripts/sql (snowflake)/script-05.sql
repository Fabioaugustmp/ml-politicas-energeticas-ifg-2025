-- =====================================================================
-- AIRBYTE INTEGRATION
-- =====================================================================
-- Start the lab_airbyte
CREATE WAREHOUSE IF NOT EXISTS LAB_WH_AIRBYTE
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

USE WAREHOUSE LAB_WH_AIRBYTE;

CREATE DATABASE LAB_PIPELINE;
CREATE SCHEMA STAGING;
CREATE ROLE AIRBYTE_DEV;

CREATE USER AIRBYTE_DEV
  DEFAULT_ROLE = AIRBYTE_DEV
  DEFAULT_WAREHOUSE = LAB_WH_AIRBYTE
  DEFAULT_NAMESPACE = LAB_PIPELINE.PUBLIC
  PASSWORD = 'mudar@123';

GRANT ROLE AIRBYTE_DEV TO USER AIRBYTE_DEV;

-- Use of the warehouse, database and schema
GRANT USAGE ON WAREHOUSE LAB_WH_AIRBYTE TO ROLE AIRBYTE_DEV;
GRANT OPERATE ON WAREHOUSE LAB_WH_AIRBYTE TO ROLE AIRBYTE_DEV;
GRANT USAGE ON DATABASE LAB_PIPELINE TO ROLE AIRBYTE_DEV;
GRANT USAGE ON SCHEMA LAB_PIPELINE.PUBLIC TO ROLE AIRBYTE_DEV;
GRANT USAGE ON SCHEMA LAB_PIPELINE.STAGING TO ROLE AIRBYTE_DEV;

-- To access to tables
GRANT SELECT, UPDATE, INSERT, DELETE ON ALL TABLES IN SCHEMA LAB_PIPELINE.PUBLIC TO ROLE AIRBYTE_DEV;
GRANT SELECT, UPDATE, INSERT, DELETE ON FUTURE TABLES IN SCHEMA LAB_PIPELINE.PUBLIC TO ROLE AIRBYTE_DEV;

GRANT SELECT, UPDATE, INSERT, DELETE ON ALL TABLES IN SCHEMA LAB_PIPELINE.STAGING TO ROLE AIRBYTE_DEV;
GRANT SELECT, UPDATE, INSERT, DELETE ON FUTURE TABLES IN SCHEMA LAB_PIPELINE.STAGING TO ROLE AIRBYTE_DEV;

-- To create schemas and tables
GRANT CREATE SCHEMA ON DATABASE LAB_PIPELINE TO ROLE AIRBYTE_DEV;
GRANT CREATE TABLE ON SCHEMA LAB_PIPELINE.PUBLIC TO ROLE AIRBYTE_DEV;
GRANT CREATE FUNCTION ON SCHEMA LAB_PIPELINE.PUBLIC TO ROLE AIRBYTE_DEV;

GRANT CREATE TABLE ON SCHEMA LAB_PIPELINE.STAGING TO ROLE AIRBYTE_DEV;
GRANT CREATE FUNCTION ON SCHEMA LAB_PIPELINE.STAGING TO ROLE AIRBYTE_DEV;


SELECT * FROM LAB_PIPELINE.STAGING.DISPONIBILIDADE_USINA_2025_08;

SELECT CURRENT_ACCOUNT(), CURRENT_REGION();




select count(*) from RAW_STAGE.INMET_STAGE_RAW;
select "Data", count(*) from RAW.STG_INMET_DATA group by "Data";

select count(*) from RAW.STG_INMET_DATA;
select * from RAW.INMET_STAGE;

select "Data", count(*) from RAW.STG_INMET_DATA group by "Data";

SELECT 
    YEAR(TO_DATE("Data", 'YYYY/MM/DD')) AS ano,
    COUNT(*) AS total_registros
FROM  RAW.STG_INMET_DATA
GROUP BY YEAR(TO_DATE("Data", 'YYYY/MM/DD'))
UNION ALL
SELECT 
    TO_CHAR(TO_DATE("Data", 'YYYY/MM/DD'), 'YYYY/MM') AS mes,
    COUNT(*) AS total_registros
FROM  RAW.STG_INMET_DATA
GROUP BY TO_CHAR(TO_DATE("Data", 'YYYY/MM/DD'), 'YYYY/MM')
ORDER BY 1;


SELECT 
    TO_CHAR(TO_DATE("Data", 'YYYY/MM/DD'), 'YYYY') AS ano,
    COUNT(*) AS total_registros
FROM RAW.STG_INMET_DATA
GROUP BY TO_CHAR(TO_DATE("Data", 'YYYY/MM/DD'), 'YYYY');




SELECT 
    TO_CHAR(TO_DATE("Data", 'YYYY/MM/DD'), 'YYYY-MM') AS mes,
    COUNT(*) AS total
FROM RAW.STG_INMET_DATA
GROUP BY TO_CHAR(TO_DATE("Data", 'YYYY/MM/DD'), 'YYYY-MM')
ORDER BY mes;



CREATE OR REPLACE TABLE CORE.STG_INMET_WMO (
    region              VARCHAR(10),
    uf                  VARCHAR(2),
    station             VARCHAR(100),
    id_wmo              VARCHAR(10),
    latitude            FLOAT,
    longitude           FLOAT,
    altitude            FLOAT
);

CREATE TABLE IF NOT EXISTS RAW.INGESTION_LOGS (
    FILENAME VARCHAR(500),
    YEAR INTEGER,
    STATUS VARCHAR(50),
    ELAPSED_SECONDS FLOAT,
    INGESTED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);



SELECT COUNT(*) FROM LAB_PIPELINE.CORE.STG_INMET_WMO
        WHERE ID_WMO = 'A002'

CREATE TABLE IF NOT EXISTS RAW.INGESTION_LOGS (
            FILENAME VARCHAR(500),
            YEAR INTEGER,
            STATUS VARCHAR(50),
            ELAPSED_SECONDS FLOAT,
            INGESTED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
        );

SELECT * FROM LAB_PIPELINE.RAW.STG_INMET_DATA

-- DROP TABLE LAB_PIPELINE.RAW.STG_INMET_DATA
        COPY INTO LAB_PIPELINE.RAW.STG_INMET_DATA
            FROM (
                -- CREATE TABLE LAB_PIPELINE.RAW.STG_INMET_DATA as 
                SELECT --'A002' AS "ID_WMO",
                   $1 AS "Data",
                   $2 AS "hora_utc",
                   $3 AS "precipitação_total_horário_(mm)",
                   $4 AS "pressao_atmosferica_ao_nivel_da_estacao_horaria_(m-b)",
                   $5 AS "pressão_atmosferica_maxna_hora_ant_(aut)_(m-b)",
                   $6 AS "pressão_atmosferica_min_na_hora_ant_(aut)_(m-b)",
                   $7 AS "radiacao_global_(kj/m²)",
                   $8 AS "temperatura_do_ar_bulbo_seco_horaria_(°c)",
                   $9 AS "temperatura_do_ponto_de_orvalho_(°c)",
                   $10 AS "temperatura_máxima_na_hora_ant_(aut)_(°c)",
                   $11 AS "temperatura_mínima_na_hora_ant_(aut)_(°c)",
                   $12 AS "temperatura_orvalho_max_na_hora_ant_(aut)_(°c)",
                   $13 AS "temperatura_orvalho_min_na_hora_ant_(aut)_(°c)",
                   $14 AS "umidade_rel_max_na_hora_ant_(aut)_(%)",
                   $15 AS "umidade_rel_min_na_hora_ant_(aut)_(%)",
                   $16 AS "umidade_relativa_do_ar_horaria_(%)",
                   $17 AS "vento_direcao_horaria_(gr)_(°_(gr))",
                   $18 AS "vento_rajada_maxima_(m/s)",
                   $19 AS "vento_velocidade_horaria_(m/s)"
                FROM @LAB_PIPELINE.RAW.STAGE_RAW/INMET_CO_GO_A002_GOIANIA_01-01-2022_A_31-12-2022.CSV
                (FILE_FORMAT => 'LAB_PIPELINE.RAW.INMET_CSV_FORMAT')
                
            );
