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
import json
import logging
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

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
    
    # 1. Locate input CSV
    if not input_csv:
        input_csv = find_input_csv("data")
        
    if not input_csv or not os.path.exists(input_csv):
        raise FileNotFoundError(
            "No CSV dataset found in /data. Please place a CSV file in /data to proceed."
        )
        
    logger.info(f"Target dataset: {input_csv}")
    spark = create_spark_session()
    
    # 2. Read with schema inference
    raw_df = spark.read.csv(input_csv, header=True, inferSchema=True)
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
        "input_dataset": os.path.basename(input_csv),
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
    
    # 7. Write Parquet
    logger.info(f"Writing cleaned data to Parquet: {output_parquet}")
    clean_df.write.mode("overwrite").parquet(output_parquet)
    
    # 8. Extract Sample Rows & Metadata for Agent Prompt
    sample_rows = [row.asDict() for row in clean_df.limit(3).collect()]
    for r in sample_rows:
        for k, v in r.items():
            if not isinstance(v, (int, float, str, bool, type(None))):
                r[k] = str(v)
                
    schema_metadata = {
        "table_name": "sales",
        "dataset_name": os.path.basename(input_csv),
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
    
    # 9. Dynamic PostgreSQL Table Creation & Loading
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = os.environ.get("POSTGRES_PORT", "5434")
    pg_db = os.environ.get("POSTGRES_DB", "business_assistant")
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres_password")
    
    import psycopg2
    from psycopg2.extras import execute_batch
    
    conn = psycopg2.connect(
        host=pg_host,
        port=int(pg_port),
        dbname=pg_db,
        user=pg_user,
        password=pg_password
    )
    cursor = conn.cursor()
    
    # Construct DDL based on discovered columns
    col_defs = ["id SERIAL PRIMARY KEY"]
    for col in clean_df.columns:
        pg_type = spark_to_postgres_type(clean_df.schema[col].dataType)
        col_defs.append(f'"{col}" {pg_type}')
    col_defs.append("created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP")
    
    create_table_sql = f"""
        DROP TABLE IF EXISTS sales CASCADE;
        CREATE TABLE sales (
            {', '.join(col_defs)}
        );
        GRANT SELECT ON TABLE sales TO sales_readonly;
    """
    cursor.execute(create_table_sql)
    conn.commit()
    logger.info("Dynamically created PostgreSQL 'sales' table matching discovered schema.")
    
    # Batch Insert Records
    raw_col_names = [f'"{c}"' for c in clean_df.columns]
    placeholders = ["%s"] * len(clean_df.columns)
    insert_sql = f"INSERT INTO sales ({', '.join(raw_col_names)}) VALUES ({', '.join(placeholders)});"
    
    records = []
    for r in clean_df.collect():
        row_vals = []
        for c in clean_df.columns:
            val = r[c]
            if val is not None and isinstance(clean_df.schema[c].dataType, (DoubleType, FloatType)):
                val = float(val)
            row_vals.append(val)
        records.append(tuple(row_vals))
        
    execute_batch(cursor, insert_sql, records, page_size=500)
    conn.commit()
    logger.info(f"Successfully loaded {len(records)} rows into PostgreSQL 'sales' table.")
    
    # Store quality report into quality_reports table
    import uuid
    report_id = f"qr_{uuid.uuid4().hex[:12]}"
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quality_reports (
            id SERIAL PRIMARY KEY,
            report_id VARCHAR(64) UNIQUE NOT NULL,
            raw_rows INT NOT NULL,
            cleaned_rows INT NOT NULL,
            duplicates_removed INT NOT NULL,
            report_data JSONB NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        GRANT SELECT ON TABLE quality_reports TO sales_readonly;
    """)
    cursor.execute("""
        INSERT INTO quality_reports (report_id, raw_rows, cleaned_rows, duplicates_removed, report_data)
        VALUES (%s, %s, %s, %s, %s);
    """, (
        report_id,
        raw_total_rows,
        cleaned_total_rows,
        duplicate_rows_detected,
        json.dumps(quality_report)
    ))
    conn.commit()

    # Recreate sales_sandbox matching newly created schema
    cursor.execute("""
        DROP TABLE IF EXISTS sales_sandbox CASCADE;
        CREATE TABLE sales_sandbox (LIKE sales INCLUDING ALL);
        INSERT INTO sales_sandbox SELECT * FROM sales;
        GRANT SELECT ON TABLE sales_sandbox TO sales_readonly;
    """)
    conn.commit()

    # Persist dynamic schema metadata and data dictionary to database
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_metadata (
            id SERIAL PRIMARY KEY,
            dataset_name VARCHAR(255) NOT NULL,
            table_name VARCHAR(255) NOT NULL DEFAULT 'sales',
            row_count INT NOT NULL DEFAULT 0,
            column_count INT NOT NULL DEFAULT 0,
            columns_info JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        GRANT SELECT ON TABLE schema_metadata TO sales_readonly;
    """)
    cursor.execute("""
        INSERT INTO schema_metadata (dataset_name, table_name, row_count, column_count, columns_info)
        VALUES (%s, %s, %s, %s, %s);
    """, (
        os.path.basename(input_csv),
        "sales",
        cleaned_total_rows,
        len(clean_df.columns),
        json.dumps(schema_metadata["columns"])
    ))
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("Successfully persisted quality report and schema metadata to PostgreSQL.")
    
    spark.stop()
    logger.info("Universal PySpark Pipeline completed successfully.")
    return quality_report

if __name__ == "__main__":
    run_sales_pipeline()
