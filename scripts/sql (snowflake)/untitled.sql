COPY INTO LAB_PIPELINE.RAW.STG_INMET_DATA (RAW_DATA)
            FROM (
                SELECT *
                FROM RAW.STG_INMET_DATA
            )
            FILE_FORMAT = (FORMAT_NAME = 'LAB_PIPELINE.RAW.INMET_CSV_FORMAT')
            ON_ERROR = 'ABORT_STATEMENT';


            SELECT * FROM LAB_PIPELINE.RAW.INMET_CSV_FORMAT;
            
            SELECT * FROM RAW.STG_INMET_DATA;
            SELECT * FROM RAW.INMET_STAGE;



            

            SELECT * FROM RAW_STAGE.INMET_STAGE_RAW;


            CREATE OR REPLACE FILE FORMAT LAB_PIPELINE.RAW.INMET_CSV_FORMAT
            TYPE = CSV
            FIELD_DELIMITER = ','
            SKIP_HEADER = 8
            ENCODING = 'ISO-8859-1' 
            DATE_FORMAT = 'YYYY/MM/DD'
            TIME_FORMAT = 'HH24MI "UTC"'
            REPLACE_INVALID_CHARACTERS = TRUE
            ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
            NULL_IF = ('', 'NULL', 'NaN');


            COPY INTO LAB_PIPELINE.RAW.STG_INMET_DATA (RAW_DATA)
            FROM (
                SELECT *
                FROM @inmet/2021/INMET_CO_GO_A002_GOIANIA_01-01-2021_A_31-12-2021.CSV
            )
            FILE_FORMAT = (FORMAT_NAME = 'LAB_PIPELINE.RAW.INMET_CSV_FORMAT')
            ON_ERROR = 'ABORT_STATEMENT'


            
CREATE OR REPLACE FILE FORMAT LAB_PIPELINE.RAW.STG_INMET_DATA
            TYPE = CSV
            FIELD_DELIMITER = ';'
            SKIP_HEADER = 8
            ENCODING = 'ISO-8859-1' 
            DATE_FORMAT = 'YYYY/MM/DD'
            TIME_FORMAT = 'HH24MI "UTC"'
            REPLACE_INVALID_CHARACTERS = TRUE
            ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
            NULL_IF = ('', 'NULL', 'NaN');
            
SELECT $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19 FROM @RAW/2021/INMET_CO_GO_A002_GOIANIA_01-01-2021_A_31-12-2021.CSV (FILE_FORMAT => LAB_PIPELINE.RAW.INMET_CSV_FORMAT);
PUT file://ml-politicas-energeticas/inmet/2021/INMET_CO_GO_A002_GOIANIA_01-01-2021_A_31-12-2021.CSV @RAW;

COPY INTO LAB_PIPELINE.RAW.STG_INMET_DATA  
            FROM (
                SELECT $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19
                FROM @RAW/2021/INMET_CO_GO_A002_GOIANIA_01-01-2021_A_31-12-2021.CSV  (FILE_FORMAT => 'LAB_PIPELINE.RAW.INMET_CSV_FORMAT')
            )
            ON_ERROR = 'ABORT_STATEMENT';

SELECT * FROM LAB_PIPELINE.RAW.STG_INMET_DATA;
DELETE FROM LAB_PIPELINE.RAW.STG_INMET_DATA;


SELECT * FROM LAB_PIPELINE.RAW.STG_INMET_DATA;

CREATE TABLE LAB_PIPELINE.RAW.STG_INMET_DATA  AS 
  SELECT $1 AS "Data",
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
FROM @STAGE_RAW/2021/INMET_CO_GO_A002_GOIANIA_01-01-2021_A_31-12-2021.CSV  (FILE_FORMAT => 'LAB_PIPELINE.RAW.INMET_CSV_FORMAT')
                               
                               
-- DROP TABLE LAB_PIPELINE.RAW.STG_INMET_DATA;
 COPY INTO LAB_PIPELINE.RAW.STG_INMET_DATA 
            FROM (
                SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
                FROM @STAGE_RAW/2021/INMET_CO_GO_A002_GOIANIA_01-01-2021_A_31-12-2021.CSV  (FILE_FORMAT => 'LAB_PIPELINE.RAW.INMET_CSV_FORMAT')
            )
            ON_ERROR = 'ABORT_STATEMENT'


            COPY INTO LAB_PIPELINE.RAW.STG_INMET_DATA 
            FROM (
                SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19
                FROM @LAB_PIPELINE.RAW.STAGE_RAW/2021/INMET_CO_GO_A002_GOIANIA_01-01-2021_A_31-12-2021.CSV  (FILE_FORMAT => 'LAB_PIPELINE.RAW.INMET_CSV_FORMAT')
            )
            ON_ERROR = 'ABORT_STATEMENT'


            SELECT * FROM LAB_PIPELINE.RAW.STG_INMET_DATA ;
            DROP TABLE LAB_PIPELINE.RAW.STG_INMET_DATA ;
            
COPY INTO LAB_PIPELINE.RAW.STG_INMET_DATA
                    FROM (
                        SELECT $1  "Data"
                           
                        FROM @STAGE_RAW/2020/INMET_CO_GO_A002_GOIANIA_01-01-2020_A_31-12-2020.CSV
                    )
                    FILE_FORMAT = (FORMAT_NAME = 'LAB_PIPELINE.RAW.INMET_CSV_FORMAT')
                    ON_ERROR = 'ABORT_STATEMENT';

            Data
            Hora UTC
            PRECIPITAÇÃO TOTAL, HORÁRIO (mm)	PRESSAO ATMOSFERICA AO NIVEL DA ESTACAO, HORARIA (mB)	PRESSÃO ATMOSFERICA MAX.NA HORA ANT. (AUT) (mB)	PRESSÃO ATMOSFERICA MIN. NA HORA ANT. (AUT) (mB)	RADIACAO GLOBAL (Kj/m²)	TEMPERATURA DO AR - BULBO SECO, HORARIA (°C)	TEMPERATURA DO PONTO DE ORVALHO (°C)	TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C)	TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)	TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C)	TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C)	UMIDADE REL. MAX. NA HORA ANT. (AUT) (%)	UMIDADE REL. MIN. NA HORA ANT. (AUT) (%)	UMIDADE RELATIVA DO AR, HORARIA (%)	VENTO, DIREÇÃO HORARIA (gr) (° (gr))	VENTO, RAJADA MAXIMA (m/s)	VENTO,
            VELOCIDADE HORARIA (m/s)
