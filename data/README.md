# Datasets Directory (`/data`)

Place any CSV dataset file (`.csv`) you want to analyze in this folder, or upload one directly via the **Add Data** button in the web app.

- Column names, types (numeric, categorical, date/time), and data quality metrics are discovered automatically by the PySpark pipeline.
- Example: drop `my_data.csv` here and run `python -m pipelines.clean_sales` (or click **Run PySpark Pipeline & Ingestion** in the UI).
