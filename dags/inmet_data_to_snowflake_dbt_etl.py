from __future__ import annotations

import logging
import time
from airflow.decorators import dag, task, task_group
from airflow.utils.task_group import TaskGroup
# Using the generic SQL operator for stability
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator 
from datetime import datetime, timedelta
import io
import boto3

# Configure logger
logger = logging.getLogger(__name__)

# Define S3 and Snowflake parameters
YEAR_INITIAL = 2001
S3_BUCKET = "ml-politicas-energeticas"
SNOWFLAKE_CONN_ID = "snowflake_default"
SNOWFLAKE_DATABASE = "LAB_PIPELINE"
DBT_PROJECT_DIR = "/usr/local/airflow/dags/dbt/inmet_project"
SNOWFLAKE_STAGE = "RAW"  # ⬅️ Correct variable for the Stage Name
SNOWFLAKE_STAGING_TABLE = f"{SNOWFLAKE_STAGE}.STG_INMET_DATA"
FULLY_QUALIFIED_TABLE = f"{SNOWFLAKE_DATABASE}.{SNOWFLAKE_STAGING_TABLE}"
FULLY_QUALIFIED_FILE_FORMAT = f"{SNOWFLAKE_DATABASE}.{SNOWFLAKE_STAGE}.INMET_CSV_FORMAT"



# Function to get the list of years dynamically
def get_years_to_process():
    """Generates the list of years from 2000 up to the current year (2025)."""
    current_year = datetime.now().year
    # NOTE: Set the end year explicitly to the current time context (2025)
    # If this DAG were run in 2026, it would include 2026.
    return list(range(YEAR_INITIAL, current_year + 1))  # começar de 2000, incluindo 2025

def get_files_in_bucket(bucket: str, prefix: str) -> list:
    """List all CSV files in a given S3 bucket with the specified prefix (year)."""
    import boto3
    s3_client = boto3.client("s3")
    paginator = s3_client.get_paginator("list_objects_v2")
    page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)

    files = []
    for page in page_iterator:
        if "Contents" in page:
            for obj in page["Contents"]:
                key = obj["Key"]
                if key.lower().endswith(".csv"):
                    files.append(key)
    return files

def get_id_wmo_from_filename(filename: str) -> str:
    """Extract ID_WMO from the filename format 'INMET_<REGION>_<STATE>_<ID_WMO>_...csv'."""
    parts = filename.split('_')
    if len(parts) >= 2:
        return parts[3]
    else:
        raise ValueError(f"Filename {filename} does not conform to expected format.")

def get_station_info_from_filename(s3_filepath: str) -> dict:
    """Extract station information from the filename format 'INMET_<REGION>_<STATE>_<ID_WMO>_...csv'."""
    s3_client = boto3.client("s3")

    logging.info(f"Fetching station info from S3 file: inmet/{s3_filepath}")
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=f'inmet/{s3_filepath}')
    content = response['Body'].read().decode('latin-1')
    file_in_memory = io.StringIO(content)

    # Lê cabeçalho de 8 linhas
    header_lines = [next(file_in_memory) for _ in range(8)]
    region = header_lines[0].split(';')[1].strip()
    uf = header_lines[1].split(';')[1].strip()
    station = header_lines[2].split(';')[1].strip()
    id_wmo = header_lines[3].split(';')[1].strip()
    latitude = header_lines[4].split(';')[1].replace(',', '.').strip()
    longitude = header_lines[5].split(';')[1].replace(',', '.').strip()
    altitude = header_lines[6].split(';')[1].replace(',', '.').strip()
    
    return {
        'id_wmo': id_wmo,
        'region': region,
        'uf': uf,
        'station': station,
        'latitude': latitude,
        'longitude': longitude,
        'altitude': altitude
    }
    
    
def insert_metadata_record(filename: str, year: int, status: str, elapsed_seconds: float):
    """Insert a metadata record into the Snowflake metadata table."""
    from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

    hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONN_ID)
    # Then insert the record
    sql = f"""
        INSERT INTO {SNOWFLAKE_DATABASE}.RAW.INGESTION_LOGS
        (FILENAME, YEAR, STATUS, ELAPSED_SECONDS, INGESTED_AT)
        VALUES ('{filename}', {year}, '{status}', {elapsed_seconds}, CURRENT_TIMESTAMP());
    """
    hook.run(sql, autocommit=True)


def insert_cod_wmo_record(filename: str, id_wmo: str):
    """Insert a record into the COD_WMO table if it doesn't exist."""
    from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

    hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONN_ID)
    sql_check = f"""
        SELECT COUNT(*) FROM {SNOWFLAKE_DATABASE}.CORE.STG_INMET_WMO
        WHERE ID_WMO = '{id_wmo}';
    """
    result = hook.get_first(sql_check)
    if result and result[0] == 0:

        station_info = get_station_info_from_filename(filename)

        region = station_info['region']
        uf = station_info['uf']
        station = station_info['station']
        latitude = float(station_info['latitude'])
        longitude = float(station_info['longitude'])
        altitude = float(station_info['altitude']) if station_info['altitude'] else 'NULL'
        

        sql_insert = f"""
            INSERT INTO {SNOWFLAKE_DATABASE}.CORE.STG_INMET_WMO (id_wmo, region, uf,
                station, latitude, longitude, altitude )
            VALUES ('{id_wmo}', '{region}', '{uf}', 
            '{station}', '{latitude}', 
            '{longitude}', '{altitude}');
        """
        hook.run(sql_insert, autocommit=True)    


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5)
}

@dag(
    dag_id="inmet_data_to_snowflake_dbt_etl",
    default_args=default_args,
    description="INMET CSV data to Snowflake, using DBT for transformations.",
    schedule_interval="@once",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["elt", "snowflake", "dbt", "s3", "taskflow"],
)
def inmet_data_to_snowflake_dbt_etl():

    
    # 1. Create a Snowflake File Format in the RAW schema
    create_file_format = SQLExecuteQueryOperator(
        task_id="create_csv_file_format",
        conn_id=SNOWFLAKE_CONN_ID,
        sql=f"""
            CREATE OR REPLACE FILE FORMAT {FULLY_QUALIFIED_FILE_FORMAT}
            TYPE = CSV
            FIELD_DELIMITER = ';'
            SKIP_HEADER = 9
            ENCODING = 'ISO-8859-1' 
            DATE_FORMAT = 'YYYY/MM/DD'
            TIME_FORMAT = 'HH24MI "UTC"'
            REPLACE_INVALID_CHARACTERS = TRUE
            ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
            NULL_IF = ('', 'NULL', 'NaN');
        """,
    )


    @task
    def generate_file_list(year: int):
        """Generate list of files to process for a specific year."""
        files_to_process = []

        # Correct prefix format for S3: "inmet/YEAR/"
        prefix = f'inmet/{year}/'
        filenames = get_files_in_bucket(S3_BUCKET, prefix)

        logger.info(f"[YEAR {year}] Generating file list for {len(filenames)} files")

        for file in filenames:
            # Extract just the filename from the full S3 key
            filename = file.split('/')[-1] if '/' in file else file            
            
            file_info = {
                'year': year,
                'filename': filename,
                's3_path': file[6:]  # relative S3 key path used by Snowflake stage without 'inmet/'
            }
            files_to_process.append(file_info)
            logger.info(f"[YEAR {year}] Added to processing list: {file_info['filename']}")
        
        logger.info(f"[YEAR {year}] Total files to process: {len(files_to_process)}")
        return files_to_process
    
    # 3. Function to execute COPY INTO for a single file
    @task
    def copy_file_to_snowflake(file_info: dict):
        """Execute Snowflake COPY INTO for a single CSV file."""
        from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
        
        start_time = time.time()
        year = file_info['year']
        filename = file_info['filename']
        s3_file_path = file_info['s3_path']   # por ex. "2024/INMET_...CSV" se seu file_info estiver assim
        # station_info = get_station_info_from_filename(s3_file_path)

        # Acessando campos
        id_wmo = get_id_wmo_from_filename(filename)      
        insert_cod_wmo_record(s3_file_path, id_wmo)
        
        
        logger.info(f"[YEAR {year}] Processing file: {filename}")
        logger.info(f"[YEAR {year}] S3 path: {s3_file_path}")
        
        # SQL to execute
        sql = f"""
            COPY INTO {FULLY_QUALIFIED_TABLE}
            FROM (
                SELECT '{id_wmo}' AS "ID_WMO",
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
                FROM @{SNOWFLAKE_DATABASE}.{SNOWFLAKE_STAGE}.STAGE_RAW/{s3_file_path}
                (FILE_FORMAT => '{FULLY_QUALIFIED_FILE_FORMAT}')
            );
        """
        
        # Execute using Snowflake Hook
        hook = SnowflakeHook(snowflake_conn_id=SNOWFLAKE_CONN_ID)
        result = hook.run(sql, autocommit=True)
        
        elapsed = time.time() - start_time
        logger.info(f"[YEAR {year}] File processed successfully in {elapsed:.2f}s")
        logger.info(f"[YEAR {year}] Query result: {result}")
        insert_metadata_record(filename, year, 'success', elapsed)
        
        return {
            'filename': filename,
            'year': year,
            'elapsed_seconds': elapsed,
            'status': 'success'
        }
    
    # 4. Workflow execution with TaskFlow API using TaskGroup per year
    # Process one year at a time sequentially
    previous_year_task = create_file_format
    
    for year in get_years_to_process():
        # Use TaskGroup class to avoid variable capture issues in loops
        with TaskGroup(group_id=f"year_{year}") as year_group:
            # Generate file list for this specific year
            files_list = generate_file_list.override(task_id=f"generate_file_list")(
                year=year
            )
            
            # Use dynamic task mapping to process all files for this year
            # Tasks will be named: year_XXXX.copy_file_to_snowflake[0], [1], etc.
            copy_results = copy_file_to_snowflake.override(task_id=f"copy_file_to_snowflake").expand(
                file_info=files_list
            )
            
            # Ensure dependency within the group
            files_list >> copy_results
        
        # Set up dependencies: previous year -> this year's tasks
        previous_year_task >> year_group
        
        # Update for next year to wait for this year's completion
        previous_year_task = year_group
    
dag = inmet_data_to_snowflake_dbt_etl()
