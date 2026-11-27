"""
Shared SQL validation, sanitization, and dialect adaptation helpers for Fixdesk.
Enforces read-only single-SELECT safety across both PostgreSQL and BigQuery.
"""

import re
from typing import Set

PROHIBITED_SQL_KEYWORDS: Set[str] = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
    "CALL", "MERGE", "INTO", "LOCK", "VACUUM", "REINDEX",
    "COPY", "ALTERUSER", "CREATEDB", "CREATEROLE", "EXPORT",
}

ALLOWED_ANALYTICS_TABLES: Set[str] = {"sales", "quality_reports", "schema_metadata"}


def validate_and_sanitize_sql(sql_query: str) -> str:
    """
    Validate that the SQL query is strictly a single, read-only SELECT statement.
    Enforces LIMIT <= 100, strips trailing semicolon, blocks comments, and prevents chaining.
    """
    if not sql_query or not sql_query.strip():
        raise ValueError("Invalid query: SQL query cannot be empty.")

    cleaned = sql_query.strip()

    if "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
        raise ValueError("Security violation: Comments ('--', '/*') are prohibited in queries.")

    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if ";" in cleaned:
        raise ValueError("Security violation: Multiple statements or semicolon chaining are prohibited.")

    tokens = re.findall(r"\b[A-Za-z0-9_]+\b", cleaned)
    if not tokens:
        raise ValueError("Invalid query: No tokens parsed.")

    first_token = tokens[0].upper()
    if first_token not in ("SELECT", "WITH"):
        raise ValueError(f"Security violation: Query must begin with SELECT. Found '{first_token}'.")

    upper_tokens = {t.upper() for t in tokens}
    intersection = upper_tokens.intersection(PROHIBITED_SQL_KEYWORDS)
    if intersection:
        forbidden = ", ".join(sorted(intersection))
        raise ValueError(f"Security violation: Mutation/DDL keyword(s) not allowed: {forbidden}")

    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", cleaned, re.IGNORECASE)
    if limit_match:
        val = int(limit_match.group(1))
        if val > 100:
            cleaned = re.sub(r"\bLIMIT\s+\d+\b", "LIMIT 100", cleaned, flags=re.IGNORECASE)
    else:
        cleaned = f"{cleaned} LIMIT 100"

    return cleaned


def validate_dml_patch(sql_patch: str, allowed_table: str = "sales_sandbox") -> str:
    """
    Validate a Support Desk remediation SQL patch before sandbox or approved production execution.
    Blocks DDL/chaining/comments and ensures only UPDATE statements run.
    """
    if not sql_patch or not sql_patch.strip():
        raise ValueError("SQL patch cannot be empty.")

    cleaned = sql_patch.strip()
    if "--" in cleaned or "/*" in cleaned or "*/" in cleaned:
        raise ValueError("Dangerous or prohibited SQL comment detected in proposed patch.")

    forbidden = {"DROP", "TRUNCATE", "ALTER", "GRANT", "REVOKE", "CREATE", "MERGE", "CALL"}
    tokens = re.findall(r"\b[A-Za-z0-9_]+\b", cleaned)
    if not tokens:
        raise ValueError("Invalid SQL patch.")
    upper_tokens = {t.upper() for t in tokens}
    bad = upper_tokens.intersection(forbidden)
    if bad and allowed_table.upper() not in upper_tokens:
        raise ValueError("Dangerous or prohibited SQL pattern detected in proposed patch.")

    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if ";" in cleaned:
        raise ValueError("Dangerous or prohibited SQL: Multiple SQL statements are prohibited in proposed patch.")
    if tokens[0].upper() != "UPDATE":
        raise ValueError(f"Only UPDATE patches are permitted, found '{tokens[0].upper()}'.")
    return cleaned


def rewrite_sql_for_bigquery(sql_query: str, project_id: str, dataset: str) -> str:
    """
    Validate SQL and pin table references strictly to `{project_id}.{dataset}.<table>`.
    Blocks cross-dataset dotted references and adapts basic Postgres identifier/cast syntax.
    """
    sanitized = validate_and_sanitize_sql(sql_query)
    upper_q = sanitized.upper()

    if "EXTERNAL_QUERY" in upper_q or "INFORMATION_SCHEMA" in upper_q:
        raise ValueError("Security violation: Cross-system or INFORMATION_SCHEMA queries are blocked.")

    # Block dotted table references outside the configured dataset
    from_join_pattern = re.compile(
        r"\b(FROM|JOIN)\s+([`\"]?[A-Za-z0-9_\-]+(?:\.[A-Za-z0-9_\-]+)+[`\"]?)",
        re.IGNORECASE,
    )
    for match in from_join_pattern.finditer(sanitized):
        ref = match.group(2).strip("`\"")
        allowed_prefixes = (f"{project_id}.{dataset}.", f"{dataset}.")
        if not ref.startswith(allowed_prefixes):
            raise ValueError(
                f"Security violation: Query must target dataset '{dataset}' only (rejected '{ref}')."
            )
        tbl = ref.split(".")[-1]
        if tbl not in ALLOWED_ANALYTICS_TABLES:
            raise ValueError(
                f"Security violation: Table '{tbl}' is not in the allowed analytics allowlist."
            )

    # Convert double-quoted identifiers (outside single-quoted literals) to BigQuery backticks
    parts = re.split(r"('(?:[^'\\]|\\.)*')", sanitized)
    converted_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            converted_parts.append(part)
        else:
            p = re.sub(r'"([A-Za-z_][A-Za-z0-9_]*)"', r"`\1`", part)
            p = re.sub(
                r"([A-Za-z0-9_`\(\)\.\*]+)::numeric\b",
                r"CAST(\1 AS NUMERIC)",
                p,
                flags=re.IGNORECASE,
            )
            converted_parts.append(p)
    bq_sql = "".join(converted_parts)

    # Qualify bare allowed table names after FROM / JOIN
    for tbl in ALLOWED_ANALYTICS_TABLES:
        bq_sql = re.sub(
            rf"\b(FROM|JOIN)\s+(?:`?{re.escape(dataset)}`?\.)?`?{tbl}`?\b",
            rf"\1 `{project_id}.{dataset}.{tbl}`",
            bq_sql,
            flags=re.IGNORECASE,
        )

    return bq_sql


def adapt_dml_for_bigquery(sql_patch: str, project_id: str, dataset: str, table_name: str) -> str:
    """Adapt a validated UPDATE patch to BigQuery Standard SQL targeting `{project_id}.{dataset}.{table_name}`."""
    cleaned = validate_dml_patch(sql_patch, allowed_table=table_name)
    parts = re.split(r"('(?:[^'\\]|\\.)*')", cleaned)
    converted = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            converted.append(part)
        else:
            converted.append(re.sub(r'"([A-Za-z_][A-Za-z0-9_]*)"', r"`\1`", part))
    bq_patch = "".join(converted)
    qualified = f"`{project_id}.{dataset}.{table_name}`"
    bq_patch = re.sub(
        r"\bUPDATE\s+(?:`?[A-Za-z0-9_\-]+`?\.)*`?(?:sales_sandbox|sales)`?\b",
        f"UPDATE {qualified}",
        bq_patch,
        count=1,
        flags=re.IGNORECASE,
    )
    if "WHERE" not in bq_patch.upper():
        bq_patch = f"{bq_patch} WHERE TRUE"
    return bq_patch
