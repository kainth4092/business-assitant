"""
PySpark Sales Data Cleaning, Quality Auditing, and PostgreSQL Loader Pipeline
-----------------------------------------------------------------------------
This script performs production-grade ETL on the BigMart Sales dataset:
1. Ingests raw CSV using PySpark.
2. Profiles initial data quality metrics (nulls, duplicates, label inconsistencies).
3. Standardizes categorical labels (e.g. 'LF' / 'low fat' -> 'Low Fat').
4. Imputes missing values in Item_Weight and Outlet_Size.
5. Removes duplicate rows and casts columns to target types.
6. Generates a comprehensive Data Quality Audit Report (JSON).
7. Persists cleaned data in Apache Parquet format.
8. Loads cleaned records into PostgreSQL 'sales' table via JDBC.
"""

import os
import json
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SalesETL")

# Set JAVA_HOME if not already configured in environment
if not os.environ.get("JAVA_HOME"):
    os.environ["JAVA_HOME"] = "/usr/lib/jvm/java-21-openjdk-amd64"

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, IntegerType
)

def create_spark_session(app_name: str = "BigMartSalesETL") -> SparkSession:
    """
    Initializes a local SparkSession configured for Java 21 compatibility
    and includes the PostgreSQL JDBC driver jar.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jar_path = os.path.join(base_dir, "pipelines", "jars", "postgresql-42.7.3.jar")
    
    builder = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.memory", "2g")
        # JVM module flags required for clean reflection under Java 17 and Java 21
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
        logger.info(f"Adding PostgreSQL JDBC jar from: {jar_path}")
        builder = builder.config("spark.jars", jar_path).config("spark.driver.extraClassPath", jar_path)
    else:
        logger.warning(f"PostgreSQL JDBC jar not found at {jar_path}. Proceeding with default Spark config.")
        
    return builder.getOrCreate()

def run_sales_pipeline(
    input_csv: str = "data/BigMart_Sales.csv",
    output_parquet: str = "data/cleaned_sales.parquet",
    report_path: str = "data/data_quality_report.json"
) -> Dict[str, Any]:
    """
    Executes the end-to-end PySpark cleaning pipeline and loads data into PostgreSQL.
    """
    logger.info("Starting PySpark Sales Data Pipeline...")
    spark = create_spark_session()
    
    # Verify input file exists; generate if missing
    if not os.path.exists(input_csv):
        logger.warning(f"{input_csv} does not exist. Triggering synthetic generator...")
        from pipelines.generate_data import generate_bigmart_sales_csv
        generate_bigmart_sales_csv(input_csv)
        
    # Define explicit raw schema for robust parsing
    raw_schema = StructType([
        StructField("Item_Identifier", StringType(), True),
        StructField("Item_Weight", DoubleType(), True),
        StructField("Item_Fat_Content", StringType(), True),
        StructField("Item_Visibility", DoubleType(), True),
        StructField("Item_Type", StringType(), True),
        StructField("Item_MRP", DoubleType(), True),
        StructField("Outlet_Identifier", StringType(), True),
        StructField("Outlet_Establishment_Year", IntegerType(), True),
        StructField("Outlet_Size", StringType(), True),
        StructField("Outlet_Location_Type", StringType(), True),
        StructField("Outlet_Type", StringType(), True),
        StructField("Item_Outlet_Sales", DoubleType(), True),
    ])
    
    # --------------------------------------------------------------------------
    # 1. READ CSV (Spark DataFrame is lazy; execution happens when actions trigger)
    # --------------------------------------------------------------------------
    logger.info(f"Reading raw sales data from: {input_csv}")
    raw_df = spark.read.csv(input_csv, header=True, schema=raw_schema)
    
    # Action: Count total raw rows
    total_raw_rows = raw_df.count()
    raw_distinct_rows = raw_df.dropDuplicates().count()
    duplicate_rows_detected = total_raw_rows - raw_distinct_rows
    
    # Profile nulls before cleaning
    null_counts_before = {}
    for col_name in raw_df.columns:
        null_count = raw_df.filter(F.col(col_name).isNull()).count()
        null_counts_before[col_name] = null_count
        
    # Profile fat content distinct labels before cleaning
    fat_content_before = [
        row["Item_Fat_Content"] for row in raw_df.select("Item_Fat_Content").distinct().collect()
    ]
    
    logger.info(f"Raw rows: {total_raw_rows}, Duplicates: {duplicate_rows_detected}")
    logger.info(f"Messy Fat Content values before: {fat_content_before}")
    logger.info(f"Null counts before: {null_counts_before}")
    
    # --------------------------------------------------------------------------
    # 2. TRANSFORMATIONS: Deduplication, String Trimming, Label Standardization
    # --------------------------------------------------------------------------
    # Step A: Remove exact duplicate rows
    deduped_df = raw_df.dropDuplicates()
    
    # Step B: Strip leading and trailing whitespace on all string columns
    string_cols = [f.name for f in deduped_df.schema.fields if isinstance(f.dataType, StringType)]
    clean_df = deduped_df
    for col_name in string_cols:
        clean_df = clean_df.withColumn(col_name, F.trim(F.col(col_name)))
        
    # Step C: Standardize Item_Fat_Content
    # Map 'LF', 'low fat', ' Low Fat ' to 'Low Fat' and 'reg', 'regular' to 'Regular'
    clean_df = clean_df.withColumn(
        "Item_Fat_Content",
        F.when(F.lower(F.col("Item_Fat_Content")).isin(["lf", "low fat"]), F.lit("Low Fat"))
        .when(F.lower(F.col("Item_Fat_Content")).isin(["reg", "regular"]), F.lit("Regular"))
        .otherwise(F.col("Item_Fat_Content"))
    )
    
    # --------------------------------------------------------------------------
    # 3. IMPUTE MISSING VALUES
    # --------------------------------------------------------------------------
    # Step A: Impute Item_Weight
    # Strategy: Use average weight for that specific Item_Identifier; if still null, use overall mean
    item_window = Window.partitionBy("Item_Identifier")
    item_mean_weight = F.avg("Item_Weight").over(item_window)
    global_mean_weight = clean_df.select(F.avg("Item_Weight")).first()[0] or 12.85
    
    clean_df = clean_df.withColumn(
        "Item_Weight",
        F.coalesce(F.col("Item_Weight"), item_mean_weight, F.lit(global_mean_weight))
    )
    
    # Step B: Impute Outlet_Size
    # Strategy: Impute based on Outlet_Type domain knowledge:
    # Grocery Store -> Small; Supermarket Type1 -> Small/Medium; Supermarket Type2/3 -> Medium
    clean_df = clean_df.withColumn(
        "Outlet_Size",
        F.when(F.col("Outlet_Size").isNull() | (F.col("Outlet_Size") == ""),
            F.when(F.col("Outlet_Type") == "Grocery Store", F.lit("Small"))
            .when(F.col("Outlet_Type") == "Supermarket Type1", F.lit("Small"))
            .when(F.col("Outlet_Type") == "Supermarket Type2", F.lit("Medium"))
            .when(F.col("Outlet_Type") == "Supermarket Type3", F.lit("Medium"))
            .otherwise(F.lit("Medium"))
        ).otherwise(F.col("Outlet_Size"))
    )
    
    # Step C: Impute 0.0 values in Item_Visibility with item-level mean visibility
    item_mean_vis = F.avg("Item_Visibility").over(item_window)
    clean_df = clean_df.withColumn(
        "Item_Visibility",
        F.when(F.col("Item_Visibility") <= 0.0, F.coalesce(item_mean_vis, F.lit(0.05)))
        .otherwise(F.col("Item_Visibility"))
    )
    
    # Round float columns for clean reporting and storage
    clean_df = clean_df.withColumn("Item_Weight", F.round(F.col("Item_Weight"), 3))
    clean_df = clean_df.withColumn("Item_Visibility", F.round(F.col("Item_Visibility"), 6))
    clean_df = clean_df.withColumn("Item_MRP", F.round(F.col("Item_MRP"), 2))
    clean_df = clean_df.withColumn("Item_Outlet_Sales", F.round(F.col("Item_Outlet_Sales"), 2))
    
    # --------------------------------------------------------------------------
    # 4. PROFILE AFTER CLEANING & GENERATE QUALITY AUDIT REPORT
    # --------------------------------------------------------------------------
    total_cleaned_rows = clean_df.count()
    null_counts_after = {}
    for col_name in clean_df.columns:
        null_count = clean_df.filter(F.col(col_name).isNull()).count()
        null_counts_after[col_name] = null_count
        
    fat_content_after = [
        row["Item_Fat_Content"] for row in clean_df.select("Item_Fat_Content").distinct().collect()
    ]
    
    # Numeric summaries
    stats = clean_df.select(
        F.min("Item_Outlet_Sales").alias("min_sales"),
        F.max("Item_Outlet_Sales").alias("max_sales"),
        F.avg("Item_Outlet_Sales").alias("avg_sales"),
        F.sum("Item_Outlet_Sales").alias("total_sales"),
        F.avg("Item_MRP").alias("avg_mrp"),
        F.countDistinct("Item_Identifier").alias("unique_items"),
        F.countDistinct("Outlet_Identifier").alias("unique_outlets")
    ).first()
    
    quality_report = {
        "status": "SUCCESS",
        "pipeline": "PySpark BigMart Sales Cleaning",
        "records_profile": {
            "raw_total_rows": total_raw_rows,
            "duplicate_rows_removed": duplicate_rows_detected,
            "cleaned_total_rows": total_cleaned_rows,
            "unique_items_count": stats["unique_items"],
            "unique_outlets_count": stats["unique_outlets"]
        },
        "null_imputation_summary": {
            "item_weight_nulls_before": null_counts_before.get("Item_Weight", 0),
            "item_weight_nulls_after": null_counts_after.get("Item_Weight", 0),
            "outlet_size_nulls_before": null_counts_before.get("Outlet_Size", 0),
            "outlet_size_nulls_after": null_counts_after.get("Outlet_Size", 0),
        },
        "label_standardization": {
            "fat_content_labels_before": fat_content_before,
            "fat_content_labels_after": fat_content_after
        },
        "sales_summary_metrics": {
            "total_revenue": round(float(stats["total_sales"]), 2),
            "average_sales_per_item": round(float(stats["avg_sales"]), 2),
            "min_sales": round(float(stats["min_sales"]), 2),
            "max_sales": round(float(stats["max_sales"]), 2),
            "average_mrp": round(float(stats["avg_mrp"]), 2)
        }
    }
    
    # Save Data Quality Report
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2)
    logger.info(f"Saved Data Quality Report to: {report_path}")
    
    # --------------------------------------------------------------------------
    # 5. WRITE CLEANED DATA TO PARQUET
    # --------------------------------------------------------------------------
    logger.info(f"Writing cleaned data to Parquet at: {output_parquet}")
    clean_df.write.mode("overwrite").parquet(output_parquet)
    logger.info("Successfully wrote Parquet file.")
    
    # --------------------------------------------------------------------------
    # 6. LOAD CLEANED DATA INTO POSTGRESQL (JDBC)
    # --------------------------------------------------------------------------
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = os.environ.get("POSTGRES_PORT", "5434")
    pg_db = os.environ.get("POSTGRES_DB", "business_assistant")
    pg_user = os.environ.get("POSTGRES_USER", "postgres")
    pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres_password")
    
    jdbc_url = f"jdbc:postgresql://{pg_host}:{pg_port}/{pg_db}"
    logger.info(f"Loading cleaned data into PostgreSQL table 'sales' at {jdbc_url}...")
    
    # Map Spark column names (CamelCase) to PostgreSQL snake_case column names
    col_mapping = {
        "Item_Identifier": "item_identifier",
        "Item_Weight": "item_weight",
        "Item_Fat_Content": "item_fat_content",
        "Item_Visibility": "item_visibility",
        "Item_Type": "item_type",
        "Item_MRP": "item_mrp",
        "Outlet_Identifier": "outlet_identifier",
        "Outlet_Establishment_Year": "outlet_establishment_year",
        "Outlet_Size": "outlet_size",
        "Outlet_Location_Type": "outlet_location_type",
        "Outlet_Type": "outlet_type",
        "Item_Outlet_Sales": "item_outlet_sales",
    }
    
    pg_df = clean_df
    for spark_col, pg_col in col_mapping.items():
        pg_df = pg_df.withColumnRenamed(spark_col, pg_col)
        
    try:
        # First attempt: JDBC write using PostgreSQL driver
        (
            pg_df.write
            .format("jdbc")
            .option("url", jdbc_url)
            .option("dbtable", "sales")
            .option("user", pg_user)
            .option("password", pg_password)
            .option("driver", "org.postgresql.Driver")
            .mode("append")
            .save()
        )
        logger.info("Successfully inserted rows into PostgreSQL via PySpark JDBC!")
    except Exception as jdbc_err:
        logger.warning(f"JDBC write encountered issue: {jdbc_err}. Executing psycopg2 batch insert fallback...")
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
        
        # Convert Spark DataFrame rows to python records
        records = [
            (
                row.item_identifier,
                float(row.item_weight),
                row.item_fat_content,
                float(row.item_visibility),
                row.item_type,
                float(row.item_mrp),
                row.outlet_identifier,
                int(row.outlet_establishment_year),
                row.outlet_size,
                row.outlet_location_type,
                row.outlet_type,
                float(row.item_outlet_sales)
            )
            for row in pg_df.collect()
        ]
        
        insert_sql = """
            INSERT INTO sales (
                item_identifier, item_weight, item_fat_content, item_visibility,
                item_type, item_mrp, outlet_identifier, outlet_establishment_year,
                outlet_size, outlet_location_type, outlet_type, item_outlet_sales
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        execute_batch(cursor, insert_sql, records, page_size=500)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Successfully inserted {len(records)} rows into PostgreSQL via fallback batch insert!")

    # Persist the Data Quality Report into PostgreSQL 'quality_reports' table
    try:
        import psycopg2
        import uuid
        report_conn = psycopg2.connect(
            host=pg_host,
            port=int(pg_port),
            dbname=pg_db,
            user=pg_user,
            password=pg_password
        )
        report_cur = report_conn.cursor()
        report_id = f"qr_{uuid.uuid4().hex[:12]}"
        report_cur.execute("""
            INSERT INTO quality_reports (report_id, raw_rows, cleaned_rows, duplicates_removed, report_data)
            VALUES (%s, %s, %s, %s, %s);
        """, (
            report_id,
            int(quality_report["records_profile"]["raw_total_rows"]),
            int(quality_report["records_profile"]["cleaned_total_rows"]),
            int(quality_report["records_profile"]["duplicate_rows_removed"]),
            json.dumps(quality_report)
        ))
        report_conn.commit()
        report_cur.close()
        report_conn.close()
        logger.info(f"Successfully persisted quality report {report_id} to PostgreSQL quality_reports table!")
    except Exception as q_err:
        logger.warning(f"Could not persist quality report to PostgreSQL: {q_err}")
        
    spark.stop()
    logger.info("PySpark Sales Pipeline completed successfully.")
    return quality_report

if __name__ == "__main__":
    run_sales_pipeline()
