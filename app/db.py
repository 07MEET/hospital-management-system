"""
db.py — Database connection and query utilities for HMS
Handles connection pooling, error mapping, and safe query execution
"""
import psycopg2
import psycopg2.extras
import psycopg2.pool
import streamlit as st
import logging
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# ── DB Config ─────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", 5432))
}

# ── Friendly Error Messages ───────────────────────────────────────────────
ERROR_MAP = {
    "duplicate key value violates unique constraint":
        "This record already exists. Please check for duplicates.",
    "violates foreign key constraint":
        "Cannot complete — a related record is missing.",
    "violates check constraint":
        "The value entered is not allowed for this field.",
    "null value in column":
        "A required field is missing. Please fill all required fields.",
    "value too long for type":
        "One of the fields is too long. Please shorten your input.",
    "invalid input syntax for type":
        "Invalid format — please check dates, numbers and special characters.",
    "slot conflict":
        "This appointment slot is already taken. Please choose a different time.",
    "connection refused":
        "Cannot connect to database. Please ensure PostgreSQL is running.",
    "already marked":
        "This record has already been processed.",
    "insufficient stock":
        "Not enough stock available for this medicine.",
}

def friendly_error(e: Exception) -> str:
    """Map psycopg2 errors to human-readable messages."""
    msg = str(e).lower()
    for key, friendly in ERROR_MAP.items():
        if key.lower() in msg:
            return friendly
    # Return first line of error, cleaned up
    first_line = str(e).split('\n')[0]
    if len(first_line) > 200:
        first_line = first_line[:200] + "..."
    return f"Database error: {first_line}"


# ── Connection ────────────────────────────────────────────────────────────
def get_connection():
    """Get a fresh database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        raise Exception(f"Cannot connect to database. Is PostgreSQL running? ({e})")


# ── Query Runners ─────────────────────────────────────────────────────────
def run_query(query: str, params=None, fetch=True):
    """
    Execute a SELECT query and return rows as list of dicts.
    Returns [] on empty, raises Exception on error.
    """
    conn = None
    try:
        conn = get_connection()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        if fetch:
            return [dict(row) for row in cur.fetchall()]
        else:
            conn.commit()
            return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Query error: {e}\nQuery: {query}\nParams: {params}")
        raise Exception(friendly_error(e))
    finally:
        if conn:
            conn.close()


def run_query_one(query: str, params=None):
    """Execute a SELECT and return the first row as dict, or None."""
    results = run_query(query, params)
    return results[0] if results else None


def call_procedure(proc_name: str, params: list):
    """Call a stored procedure with parameters."""
    conn = None
    try:
        conn = get_connection()
        cur  = conn.cursor()
        placeholders = ','.join(['%s'] * len(params))
        cur.execute(f"CALL {proc_name}({placeholders})", params)
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Procedure error: {proc_name}({params}) — {e}")
        raise Exception(friendly_error(e))
    finally:
        if conn:
            conn.close()


def call_function(func_name: str, params: list):
    """Call a SQL function and return its result."""
    conn = None
    try:
        conn = get_connection()
        cur  = conn.cursor()
        placeholders = ','.join(['%s'] * len(params))
        cur.execute(f"SELECT {func_name}({placeholders})", params)
        result = cur.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Function error: {func_name} — {e}")
        raise Exception(friendly_error(e))
    finally:
        if conn:
            conn.close()


def run_transaction(queries: list):
    """
    Run multiple queries in a single transaction.
    queries: list of (query_string, params) tuples
    Rolls back all if any fails.
    """
    conn = None
    try:
        conn = get_connection()
        cur  = conn.cursor()
        for query, params in queries:
            cur.execute(query, params)
        conn.commit()
        return True
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Transaction error: {e}")
        raise Exception(friendly_error(e))
    finally:
        if conn:
            conn.close()


def test_connection() -> tuple[bool, str]:
    """Test DB connectivity. Returns (success, message)."""
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        conn.close()
        return True, f"Connected — {version[:40]}"
    except Exception as e:
        return False, str(e)