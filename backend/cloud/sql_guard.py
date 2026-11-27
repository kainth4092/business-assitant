"""
Shared SQL validation, sanitization, and dialect adaptation helpers for Fixdesk.
Enforces read-only single-SELECT safety across both PostgreSQL and BigQuery.
"""

import re
from typing import Dict, List, Optional, Set, Tuple

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


def is_bigquery_sandbox_dml_error(exc: Exception) -> bool:
    """
    Detect BigQuery Sandbox (no-billing / free-tier) errors rejecting DML or streaming inserts.
    """
    msg = str(exc).lower()
    if "billing has not been enabled" in msg or "enable billing" in msg:
        return True
    if "free tier" in msg and ("dml" in msg or "streaming" in msg or "not allowed" in msg):
        return True
    if "dml" in msg and ("sandbox" in msg or "not supported" in msg or "billing" in msg):
        return True
    return False


def _split_top_level(text: str, delimiter: str = ",") -> List[str]:
    """Split `text` on `delimiter` only outside quotes, backticks, and parentheses."""
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    in_single = False
    in_double = False
    in_backtick = False
    escape = False

    for ch in text:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == "\\" and in_single:
            buf.append(ch)
            escape = True
            continue
        if ch == "'" and not in_double and not in_backtick:
            in_single = not in_single
        elif ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
        elif not in_single and not in_double and not in_backtick:
            if ch == "(":
                depth += 1
            elif ch == ")" and depth > 0:
                depth -= 1
            elif ch == delimiter and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
                continue
        buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _find_top_level_keyword(text: str, keyword: str) -> int:
    """Return index of top-level SQL keyword (outside quotes/backticks/parens), or -1."""
    upper = text.upper()
    kw = keyword.upper()
    kw_len = len(kw)
    depth = 0
    in_single = False
    in_double = False
    in_backtick = False
    escape = False
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if ch == "\\" and in_single:
            escape = True
            i += 1
            continue
        if ch == "'" and not in_double and not in_backtick:
            in_single = not in_single
        elif ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
        elif ch == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
        elif not in_single and not in_double and not in_backtick:
            if ch == "(":
                depth += 1
            elif ch == ")" and depth > 0:
                depth -= 1
            elif depth == 0 and upper[i:i + kw_len] == kw:
                before_ok = (i == 0) or not (text[i - 1].isalnum() or text[i - 1] == "_")
                after_idx = i + kw_len
                after_ok = (after_idx >= n) or not (text[after_idx].isalnum() or text[after_idx] == "_")
                if before_ok and after_ok:
                    return i
        i += 1
    return -1


def _to_bq_identifiers(sql_fragment: str) -> str:
    """Convert double-quoted identifiers outside single-quoted literals to backticks."""
    parts = re.split(r"('(?:[^'\\]|\\.)*')", sql_fragment)
    out = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            out.append(part)
        else:
            out.append(re.sub(r'"([A-Za-z_][A-Za-z0-9_]*)"', r"`\1`", part))
    return "".join(out)


def parse_update_patch_for_ctas(sql_patch: str) -> Tuple[Dict[str, str], Optional[str]]:
    """
    Parse a validated single-table `UPDATE <table> SET <col>=<expr>, ... [WHERE <cond>]`
    into `(assignments_by_col, where_condition)` normalized for BigQuery Standard SQL.
    """
    cleaned = validate_dml_patch(sql_patch, allowed_table="sales_sandbox")
    bq_text = _to_bq_identifiers(cleaned)

    set_idx = _find_top_level_keyword(bq_text, "SET")
    if set_idx < 0:
        raise ValueError("Cannot convert UPDATE to CTAS fallback: missing SET clause.")

    after_set = bq_text[set_idx + 3:].strip()
    where_idx = _find_top_level_keyword(after_set, "WHERE")
    if where_idx >= 0:
        set_clause = after_set[:where_idx].strip()
        where_clause = after_set[where_idx + 5:].strip() or None
    else:
        set_clause = after_set
        where_clause = None

    assignments: Dict[str, str] = {}
    for item in _split_top_level(set_clause, ","):
        eq_parts = _split_top_level(item, "=")
        if len(eq_parts) != 2:
            raise ValueError(f"Cannot parse SET assignment '{item}' for CTAS fallback.")
        col_name = eq_parts[0].strip().strip("`").strip('"')
        expr = eq_parts[1].strip()
        if not col_name or not expr:
            raise ValueError(f"Invalid SET assignment '{item}' for CTAS fallback.")
        assignments[col_name] = expr

    if not assignments:
        raise ValueError("No column assignments found in UPDATE patch for CTAS fallback.")
    return assignments, where_clause


def build_ctas_from_update(
    sql_patch: str,
    table_columns: List[str],
    source_fq_table: str,
    target_fq_table: str,
) -> Tuple[str, str]:
    """
    Translate a single-table UPDATE patch into a BigQuery Sandbox-compatible
    `(count_affected_sql, CREATE OR REPLACE TABLE ... AS SELECT ...)` pair.
    """
    if not table_columns:
        raise ValueError("Cannot build CTAS fallback without source table column metadata.")

    assignments, where_clause = parse_update_patch_for_ctas(sql_patch)
    assignments_lower = {k.lower(): v for k, v in assignments.items()}
    known_lower = {c.lower() for c in table_columns}
    unknown = [k for k in assignments if k.lower() not in known_lower]
    if unknown:
        raise ValueError(f"CTAS fallback rejected unknown column(s): {', '.join(unknown)}")

    select_exprs: List[str] = []
    for col in table_columns:
        key = col.lower()
        if key in assignments_lower:
            new_expr = assignments_lower[key]
            if where_clause and where_clause.upper() != "TRUE":
                select_exprs.append(
                    f"CASE WHEN ({where_clause}) THEN ({new_expr}) ELSE `{col}` END AS `{col}`"
                )
            else:
                select_exprs.append(f"({new_expr}) AS `{col}`")
        else:
            select_exprs.append(f"`{col}`")

    where_pred = where_clause or "TRUE"
    count_sql = f"SELECT COUNT(*) AS affected FROM `{source_fq_table}` WHERE {where_pred}"
    ctas_sql = (
        f"CREATE OR REPLACE TABLE `{target_fq_table}` AS "
        f"SELECT {', '.join(select_exprs)} FROM `{source_fq_table}`"
    )
    return count_sql, ctas_sql
