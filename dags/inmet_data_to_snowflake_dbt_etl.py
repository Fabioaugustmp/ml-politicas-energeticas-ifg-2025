from __future__ import annotations

import pendulum
import logging
import time
from airflow.models.dag import DAG
from airflow.utils.dates import days_ago
from airflow.decorators import dag, task, task_group
from airflow.utils.task_group import TaskGroup
# Using the generic SQL operator for stability
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator 
from datetime import datetime, timedelta

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
        s3_file_path = file_info['s3_path']
        filename = file_info['filename']
        
        logger.info(f"[YEAR {year}] Processing file: {filename}")
        logger.info(f"[YEAR {year}] S3 path: {s3_file_path}")
        
        # SQL to execute
        sql = f"""
            COPY INTO {FULLY_QUALIFIED_TABLE}
            FROM (
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
