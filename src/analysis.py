"""
Queries the SQLite database to produce the Smart Money Convergence analysis and supporting outputs.
"""

import logging
import os
import sqlite3
import pandas as pd
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """
    Returns a SQLite connection to DB_PATH with row_factory set to sqlite3.Row.
    
    Returns:
        sqlite3.Connection: Database connection object.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_convergence_signals(period: str, min_funds: int = 3) -> pd.DataFrame:
    """
    Queries Fact_Holdings joined to Dim_Security and Dim_Fund, groups by security,
    and filters where COUNT(DISTINCT fund_id) >= min_funds and qoq_change_flag IN ('NEW','INCREASED').
    Excludes option positions (put_call = 'Put' or 'Call') and EXITED rows so only common equity counts.
    
    Expected SQL logic:
    SELECT s.cusip, s.ticker, s.company_name, s.sector,
           COUNT(DISTINCT f.fund_id) AS funds_buying,
           SUM(h.value_usd) AS total_value_usd
    FROM Fact_Holdings h
    JOIN Dim_Security s ON h.security_id = s.security_id
    JOIN Dim_Fund f ON h.fund_id = f.fund_id
    WHERE h.period = ?
      AND h.qoq_change_flag IN ('NEW', 'INCREASED')
      AND (h.put_call IS NULL OR h.put_call = '')
      AND h.value_usd > 0
    GROUP BY s.security_id
    HAVING COUNT(DISTINCT f.fund_id) >= ?
    
    Args:
        period (str): The reporting period (e.g., '2026-Q2').
        min_funds (int): Minimum number of independent funds for a convergence signal. Defaults to 3.
        
    Returns:
        pd.DataFrame: A DataFrame containing the convergence signals.
    """
    query = """
        SELECT
            s.cusip,
            s.ticker,
            s.company_name,
            s.sector,
            COUNT(DISTINCT f.fund_id) AS funds_buying,
            SUM(h.value_usd) AS total_value_usd,
            GROUP_CONCAT(DISTINCT f.name) AS funds
        FROM Fact_Holdings h
        JOIN Dim_Security s ON h.security_id = s.security_id
        JOIN Dim_Fund f ON h.fund_id = f.fund_id
        WHERE h.period = ?
          AND h.qoq_change_flag IN ('NEW', 'INCREASED')
          AND (h.put_call IS NULL OR h.put_call = '')
          AND h.value_usd > 0
        GROUP BY s.security_id, s.cusip, s.ticker, s.company_name, s.sector
        HAVING COUNT(DISTINCT f.fund_id) >= ?
        ORDER BY funds_buying DESC, total_value_usd DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=(period, min_funds))


def get_qoq_new_positions(period: str) -> pd.DataFrame:
    """
    Returns all holdings where qoq_change_flag = 'NEW' for the given period,
    joined with fund and security names.
    
    Args:
        period (str): The reporting period.
        
    Returns:
        pd.DataFrame: A DataFrame containing the new positions.
    """
    query = """
        SELECT
            f.name AS fund_name,
            s.cusip,
            s.ticker,
            s.company_name,
            h.put_call,
            h.value_usd,
            h.shares,
            h.pct_of_portfolio
        FROM Fact_Holdings h
        JOIN Dim_Security s ON h.security_id = s.security_id
        JOIN Dim_Fund f ON h.fund_id = f.fund_id
        WHERE h.period = ?
          AND h.qoq_change_flag = 'NEW'
          AND h.value_usd > 0
        ORDER BY h.value_usd DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=(period,))


def get_top_holdings_by_aum(period: str, top_n: int = 20) -> pd.DataFrame:
    """
    Returns top N securities ranked by total value_usd across all funds for a given period,
    excluding EXITED positions and options.
    
    Args:
        period (str): The reporting period.
        top_n (int): Number of top holdings to return. Defaults to 20.
        
    Returns:
        pd.DataFrame: A DataFrame of top holdings by AUM.
    """
    # Exclude options and EXITED positions so AUM and fund counts only reflect active equity holdings
    query = """
        SELECT
            s.cusip,
            s.ticker,
            s.company_name,
            SUM(h.value_usd) AS total_aum,
            COUNT(DISTINCT h.fund_id) AS funds_holding
        FROM Fact_Holdings h
        JOIN Dim_Security s ON h.security_id = s.security_id
        WHERE h.period = ?
          AND (h.put_call IS NULL OR h.put_call = '')
          AND (h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED')
          AND h.value_usd > 0
        GROUP BY s.security_id, s.cusip, s.ticker, s.company_name
        ORDER BY total_aum DESC
        LIMIT ?
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=(period, top_n))


def get_fund_concentration(fund_name: str, period: str) -> pd.DataFrame:
    """
    Returns the top 10 positions for a specific fund as a percentage of that fund's total portfolio value,
    excluding EXITED positions.
    
    Args:
        fund_name (str): The name of the fund.
        period (str): The reporting period.
        
    Returns:
        pd.DataFrame: A DataFrame detailing the fund's concentration.
    """
    query = """
        SELECT
            s.cusip,
            s.ticker,
            s.company_name,
            h.put_call,
            h.value_usd,
            h.shares,
            h.pct_of_portfolio,
            h.qoq_change_flag
        FROM Fact_Holdings h
        JOIN Dim_Security s ON h.security_id = s.security_id
        JOIN Dim_Fund f ON h.fund_id = f.fund_id
        WHERE f.name = ?
          AND h.period = ?
          AND (h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED')
          AND h.value_usd > 0
        ORDER BY h.value_usd DESC
        LIMIT 10
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=(fund_name, period))


def export_to_csv(df: pd.DataFrame, filename: str) -> None:
    """
    Saves DataFrame to the output/ folder.
    
    Args:
        df (pd.DataFrame): Data to export.
        filename (str): Name of the CSV file.
    """
    os.makedirs("output", exist_ok=True)
    out_path = filename if os.path.dirname(filename) else os.path.join("output", filename)
    df.to_csv(out_path, index=False)
    logger.info("Exported %d rows to %s", len(df), out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df_signals = get_convergence_signals("2026-Q2", min_funds=3)
    print(df_signals)


