"""
Universal Schema-Agnostic PySpark Data Cleaning, Quality Auditing, and PostgreSQL Loader
-----------------------------------------------------------------------------------------
This pipeline operates on ANY uploaded CSV file placed in /data:
1. Automatically discovers files in /data.
2. Infers schema, data types (numeric, categorical, datetime, text), and profiles initial quality.
3. Performs generic, schema-agnostic PySpark cleaning:
   - Removes duplicate rows
   - Trims whitespace and normalizes string labels
   - Imputes numeric nulls with column median/mean
   - Imputes categorical nulls with 'Unknown'
4. Produces a comprehensive Data Quality Audit Report (JSON).
5. Persists cleaned data in Apache Parquet format.
6. Dynamically constructs the PostgreSQL 'sales' table schema and loads cleaned data via JDBC/batch insert.
7. Saves schema metadata for dynamic agent SQL generation and frontend telemetry.
"""

import os
import re
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("UniversalETL")

# Set JAVA_HOME if not already configured in environment
if not os.environ.get("JAVA_HOME"):
    os.environ["JAVA_HOME"] = "/usr/lib/jvm/java-21-openjdk-amd64"

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StringType, DoubleType, FloatType, IntegerType, LongType,
    DecimalType, DateType, TimestampType, BooleanType
)

def create_spark_session(app_name: str = "UniversalDataETL") -> SparkSession:
    """Initializes a local SparkSession configured for Java 21 & PostgreSQL JDBC."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jar_path = os.path.join(base_dir, "pipelines", "jars", "postgresql-42.7.3.jar")
    
    builder = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "2g")
        .config("spark.driver.extraJavaOptions", 
                "--add-opens=java.base/java.lang=ALL-UNNAMED "
                "--add-opens=java.base/java.util=ALL-UNNAMED "
                "--add-opens=java.base/java.nio=ALL-UNNAMED "
                "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED")
        .config("spark.executor.extraJavaOptions",
                "--add-opens=java.base/java.lang=ALL-UNNAMED "
                "--add-opens=java.base/java.util=ALL-UNNAMED "
                "--add-opens=java.base/java.nio=ALL-UNNAMED "
                "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.parquet.outputTimestampType", "TIMESTAMP_MICROS")
    )
    
    if os.path.exists(jar_path):
        builder = builder.config("spark.jars", jar_path).config("spark.driver.extraClassPath", jar_path)
    return builder.getOrCreate()

def sanitize_column_name(col_name: str) -> str:
    """Converts raw column name into a clean, safe SQL identifier (snake_case)."""
    s = col_name.strip()
    s = re.sub(r"[^\w\s]", "_", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    if not s or s[0].isdigit():
        s = f"col_{s}"
    return s

def spark_to_postgres_type(dtype) -> str:
    """Maps a PySpark DataType to an appropriate PostgreSQL column type."""
    if isinstance(dtype, (IntegerType, LongType)):
        return "BIGINT"
    elif isinstance(dtype, (DoubleType, FloatType, DecimalType)):
        return "NUMERIC(14, 4)"
    elif isinstance(dtype, DateType):
        return "DATE"
    elif isinstance(dtype, TimestampType):
        return "TIMESTAMP WITH TIME ZONE"
    elif isinstance(dtype, BooleanType):
        return "BOOLEAN"
    else:
        return "TEXT"

def find_input_csv(data_dir: str = "data") -> Optional[str]:
    """Finds the first available CSV file in the data directory."""
    if not os.path.exists(data_dir):
        return None
    csv_candidates = [
        os.path.join(data_dir, f) for f in os.listdir(data_dir)
        if f.lower().endswith(".csv") and not f.startswith(".")
    ]
    return sorted(csv_candidates)[0] if csv_candidates else None

def run_sales_pipeline(
    input_csv: Optional[str] = None,
    output_parquet: str = "data/cleaned_sales.parquet",
    report_path: str = "data/data_quality_report.json",
    metadata_path: str = "data/schema_metadata.json"
) -> Dict[str, Any]:
    """
    Executes universal schema discovery, generic cleaning, Parquet export,
    and dynamic PostgreSQL persistence for ANY uploaded tabular CSV dataset.
    """
    logger.info("Starting Universal Data Cleaning & Ingestion Pipeline...")
    
    # 1. Locate input CSV (supports local data/ or gs://<bucket>/raw/ via FileStore)
    from backend.cloud.factories import get_file_store, get_sales_store

    file_store = get_file_store()
    if not input_csv:
        input_csv = find_input_csv("data")
        if not input_csv and file_store.backend_name == "gcp":
            remote_csvs = file_store.list_files("raw", extensions=(".csv",))
            if remote_csvs:
                input_csv = remote_csvs[0]

    if not input_csv:
        raise FileNotFoundError(
            "No CSV dataset found in /data or GCS raw/. Please place or upload a CSV file to proceed."
        )

    dataset_filename = os.path.basename(input_csv)
    local_csv_path = file_store.ensure_local_copy(input_csv)
    if not os.path.exists(local_csv_path):
        raise FileNotFoundError(
            f"Input CSV dataset '{input_csv}' could not be located locally or downloaded."
        )

    logger.info(f"Target dataset: {input_csv} (local Spark path: {local_csv_path})")
    spark = create_spark_session()

    # 2. Read with schema inference (supports multi-line quoted text fields)
    raw_df = spark.read.csv(
        local_csv_path,
        header=True,
        inferSchema=True,
        multiLine=True,
        escape='"',
    )
    raw_total_rows = raw_df.count()
    raw_distinct_rows = raw_df.dropDuplicates().count()
    duplicate_rows_detected = raw_total_rows - raw_distinct_rows
    
    # 3. Column name sanitization mapping
    col_mapping = {}
    used_names = set()
    for col in raw_df.columns:
        clean = sanitize_column_name(col)
        # Avoid collisions
        counter = 1
        orig_clean = clean
        while clean in used_names:
            clean = f"{orig_clean}_{counter}"
            counter += 1
        used_names.add(clean)
        col_mapping[col] = clean
        
    # Rename columns in raw_df
    normalized_df = raw_df
    for raw_col, clean_col in col_mapping.items():
        normalized_df = normalized_df.withColumnRenamed(raw_col, clean_col)
        
    # Profile nulls before cleaning
    null_counts_before = {}
    for col in normalized_df.columns:
        null_counts_before[col] = normalized_df.filter(F.col(col).isNull()).count()
        
    # 4. Classify columns by inferred types
    numeric_cols = []
    string_cols = []
    date_cols = []
    for field in normalized_df.schema.fields:
        if isinstance(field.dataType, (IntegerType, LongType, DoubleType, FloatType, DecimalType)):
            numeric_cols.append(field.name)
        elif isinstance(field.dataType, (DateType, TimestampType)):
            date_cols.append(field.name)
        elif isinstance(field.dataType, StringType):
            string_cols.append(field.name)
            
    logger.info(f"Discovered {len(normalized_df.columns)} columns: "
                f"{len(numeric_cols)} numeric, {len(string_cols)} string, {len(date_cols)} date/time.")
                
    # 5. Generic Cleaning Transformations
    clean_df = normalized_df.dropDuplicates()
    
    # A. Trim whitespace and clean string columns
    for sc in string_cols:
        clean_df = clean_df.withColumn(sc, F.trim(F.col(sc)))
        # Standardize inconsistent categorical labels / abbreviations (e.g. LF/low fat -> Low Fat, reg/regular -> Regular)
        clean_df = clean_df.withColumn(
            sc,
            F.when(F.lower(F.col(sc)).isin("lf", "low fat"), F.lit("Low Fat"))
            .when(F.lower(F.col(sc)).isin("reg", "regular"), F.lit("Regular"))
            .otherwise(F.col(sc))
        )
        # Replace empty strings with null for uniform imputation
        clean_df = clean_df.withColumn(
            sc, F.when(F.col(sc) == "", None).otherwise(F.col(sc))
        )
        # Impute categorical nulls with 'Unknown'
        clean_df = clean_df.withColumn(sc, F.coalesce(F.col(sc), F.lit("Unknown")))
        
    # B. Impute numeric nulls with column median/mean
    for nc in numeric_cols:
        avg_val = clean_df.select(F.avg(F.col(nc))).first()[0]
        if avg_val is not None:
            clean_df = clean_df.withColumn(
                nc, F.coalesce(F.col(nc), F.lit(round(float(avg_val), 4)))
            )
        else:
            clean_df = clean_df.withColumn(nc, F.coalesce(F.col(nc), F.lit(0)))
            
    cleaned_total_rows = clean_df.count()
    
    # Profile nulls after cleaning
    null_counts_after = {}
    for col in clean_df.columns:
        null_counts_after[col] = clean_df.filter(F.col(col).isNull()).count()
        
    # 6. Generate Summaries for Quality Report
    numeric_summaries = {}
    for nc in numeric_cols:
        stat_row = clean_df.select(
            F.min(F.col(nc)).alias("min"),
            F.max(F.col(nc)).alias("max"),
            F.avg(F.col(nc)).alias("avg"),
            F.sum(F.col(nc)).alias("sum")
        ).first()
        numeric_summaries[nc] = {
            "min": round(float(stat_row["min"]), 2) if stat_row["min"] is not None else 0.0,
            "max": round(float(stat_row["max"]), 2) if stat_row["max"] is not None else 0.0,
            "avg": round(float(stat_row["avg"]), 2) if stat_row["avg"] is not None else 0.0,
            "sum": round(float(stat_row["sum"]), 2) if stat_row["sum"] is not None else 0.0,
        }
        
    categorical_summaries = {}
    for sc in string_cols[:6]:  # Profile up to first 6 categorical columns
        top_rows = (
            clean_df.groupBy(sc)
            .count()
            .orderBy(F.desc("count"))
            .limit(5)
            .collect()
        )
        categorical_summaries[sc] = {
            "distinct_count": clean_df.select(sc).distinct().count(),
            "top_values": [{row[sc]: row["count"]} for row in top_rows]
        }
        
    quality_report = {
        "status": "SUCCESS",
        "pipeline": "PySpark Universal CSV Cleaning & Quality Audit",
        "input_dataset": dataset_filename,
        "records_profile": {
            "raw_total_rows": raw_total_rows,
            "duplicate_rows_removed": duplicate_rows_detected,
            "cleaned_total_rows": cleaned_total_rows,
            "column_count": len(clean_df.columns),
            "numeric_column_count": len(numeric_cols),
            "categorical_column_count": len(string_cols),
        },
        "null_imputation_summary": {
            "total_nulls_before": sum(null_counts_before.values()),
            "total_nulls_after": sum(null_counts_after.values()),
            "columns_imputed": [
                c for c in clean_df.columns
                if null_counts_before.get(c, 0) > null_counts_after.get(c, 0)
            ]
        },
        "columns_profile": [
            {
                "name": col,
                "type": str(clean_df.schema[col].dataType),
                "nulls_before": null_counts_before.get(col, 0),
                "nulls_after": null_counts_after.get(col, 0)
            }
            for col in clean_df.columns
        ],
        "numeric_summaries": numeric_summaries,
        "categorical_summaries": categorical_summaries
    }
    
    # Save Data Quality Report
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2)
    logger.info(f"Saved Data Quality Report to: {report_path}")
    
    # 7. Write Parquet locally & optionally upload to GCS clean/
    logger.info(f"Writing cleaned data to Parquet: {output_parquet}")
    clean_df.write.mode("overwrite").parquet(output_parquet)

    parquet_target = output_parquet
    if file_store.backend_name == "gcp":
        parquet_target = file_store.upload_from_local(
            output_parquet, "clean", remote_name=os.path.basename(output_parquet)
        )
        logger.info(f"Uploaded cleaned Parquet to GCS: {parquet_target}")

    # 8. Extract Sample Rows & Metadata for Agent Prompt
    sample_rows = [row.asDict() for row in clean_df.limit(3).collect()]
    for r in sample_rows:
        for k, v in r.items():
            if not isinstance(v, (int, float, str, bool, type(None))):
                r[k] = str(v)

    schema_metadata = {
        "table_name": "sales",
        "dataset_name": dataset_filename,
        "row_count": cleaned_total_rows,
        "columns": [
            {
                "name": col,
                "type": spark_to_postgres_type(clean_df.schema[col].dataType),
                "is_numeric": col in numeric_cols,
                "is_categorical": col in string_cols
            }
            for col in clean_df.columns
        ],
        "numeric_columns": numeric_cols,
        "categorical_columns": string_cols,
        "sample_rows": sample_rows
    }

    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(schema_metadata, f, indent=2)
    logger.info(f"Saved Schema Metadata to: {metadata_path}")

    # 9. Persist cleaned sales, sandbox mirror, quality report, and schema metadata via SalesStore
    sales_store = get_sales_store()
    load_res = sales_store.load_sales_from_parquet(
        parquet_uri_or_path=parquet_target,
        schema_metadata=schema_metadata,
        quality_report=quality_report,
        df=clean_df,
    )
    logger.info(f"SalesStore ({sales_store.backend_name}) load completed: {load_res}")

    spark.stop()
    logger.info("Universal PySpark Pipeline completed successfully.")
    return quality_report

if __name__ == "__main__":
    run_sales_pipeline()
