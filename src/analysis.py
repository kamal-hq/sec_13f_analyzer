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


ETF_SQL_CONDITION = """(
    UPPER(COALESCE(s.company_name, '')) LIKE '%ISHARES%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%SPDR%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%VANGUARD%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%INVESCO%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%PROSHARES%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%DIREXION%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%VANECK%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%WISDOMTREE%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%SCHWAB STRATEGIC%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%FIRST TR%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%GLOBAL X%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%ARK ETF%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '% ETF%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE 'ETF %'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%INDEX FD%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%EXCHANGE TRADED%'
    OR UPPER(COALESCE(s.company_name, '')) LIKE '%EXCH TRADED%'
    OR UPPER(COALESCE(s.security_class, '')) LIKE '%ETF%'
    OR UPPER(COALESCE(s.ticker, '')) IN (
        'IVV', 'SPY', 'VOO', 'QQQ', 'IWM', 'DIA', 'EEM', 'TLT', 'GLD', 'SLV',
        'HYG', 'LQD', 'XLF', 'XLK', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU', 'XLY',
        'XLB', 'XLC', 'XLRE', 'SMH', 'SOXX', 'EWZ', 'FXI', 'KWEB', 'ARKK',
        'IBIT', 'FBTC', 'GBTC', 'ETHA', 'BITO', 'VTI', 'VEA', 'VWO', 'IEFA',
        'EFA', 'AGG', 'BND', 'JNK', 'EMB', 'TIP', 'SHY', 'IEF', 'GOVT', 'MUB',
        'RSP', 'MDY', 'IJR', 'IJH', 'IWF', 'IWD', 'IWO', 'IWN', 'ACWI', 'VXUS',
        'URA', 'USO', 'UNG', 'KBE', 'KRE', 'XBI', 'XME', 'RWL'
    )
)"""


def get_convergence_signals(
    period: str,
    min_funds: int = 4,
    min_pct_increase: float = 0.10,
    min_added_value: int = 1_000_000,
    fund_types: list[str] | None = None,
    include_etfs: bool = False,
) -> pd.DataFrame:
    """
    Identifies Smart Money Convergence signals for a reporting period on split-adjusted shares.
    A fund counts as a "buyer" of a security only if:
      1. Its position is NEW, OR its split-adjusted shares increased by at least min_pct_increase (10%) QoQ, AND
      2. The dollar value added is at least min_added_value ($1,000,000), computed as
         shares_added * current_period_price (where price = value_usd / shares).
      3. Option positions (put_call = 'Put' or 'Call') and ETFs/index trusts are excluded;
         only common operating equity counts.

    Args:
        period (str): The reporting period (e.g., '2026-Q2').
        min_funds (int): Minimum number of independent buying funds. Defaults to 4.
        min_pct_increase (float): Minimum QoQ share increase fraction for existing positions. Defaults to 0.10.
        min_added_value (int): Minimum dollar value added in USD. Defaults to 1_000_000.
        fund_types (list[str] | None): Optional list of fund_type values to filter Dim_Fund.
        include_etfs (bool): If False (default), excludes ETFs and index trusts.

    Returns:
        pd.DataFrame: Convergence signals with columns:
            cusip, ticker, company_name, sector, funds_buying, funds, total_dollars_added, fund_type_breakdown.
    """
    with get_connection() as conn:
        fund_type_clause = ""
        params: list = [period, period, min_pct_increase, min_added_value]

        effective_min_funds = min_funds
        if fund_types:
            placeholders = ", ".join(["?"] * len(fund_types))
            fund_type_clause = f"AND f.fund_type IN ({placeholders})"
            params.extend(fund_types)

            count_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM Dim_Fund f WHERE f.fund_type IN ({placeholders})",
                tuple(fund_types),
            ).fetchone()
            matching_funds = int(count_row["cnt"]) if count_row else 0
            if matching_funds > 0 and effective_min_funds >= matching_funds:
                effective_min_funds = max(2, matching_funds - 1)

        params.append(effective_min_funds)
        etf_clause = "" if include_etfs else f"AND NOT {ETF_SQL_CONDITION}"

        query = f"""
            WITH prior_period AS (
                SELECT MAX(period) AS prev_period
                FROM Fact_Holdings
                WHERE period < ?
            ),
            qualified_buyers AS (
                SELECT
                    h.security_id,
                    s.cusip,
                    s.ticker,
                    s.company_name,
                    s.sector,
                    f.fund_id,
                    f.name AS fund_name,
                    f.fund_type,
                    (h.shares - COALESCE(prev.shares, 0)) * (CAST(h.value_usd AS REAL) / h.shares) AS added_value_usd
                FROM Fact_Holdings h
                JOIN Dim_Security s ON h.security_id = s.security_id
                JOIN Dim_Fund f ON h.fund_id = f.fund_id
                LEFT JOIN Fact_Holdings prev
                    ON prev.fund_id = h.fund_id
                   AND prev.security_id = h.security_id
                   AND COALESCE(prev.put_call, '') = COALESCE(h.put_call, '')
                   AND prev.period = (SELECT prev_period FROM prior_period)
                   AND prev.value_usd > 0
                WHERE h.period = ?
                  AND (h.put_call IS NULL OR h.put_call = '')
                  AND h.value_usd > 0
                  AND h.shares > 0
                  AND (
                      h.qoq_change_flag = 'NEW'
                      OR (prev.shares > 0 AND (h.shares - prev.shares) * 1.0 / prev.shares >= ?)
                  )
                  AND ((h.shares - COALESCE(prev.shares, 0)) * (CAST(h.value_usd AS REAL) / h.shares)) >= ?
                  {etf_clause}
                  {fund_type_clause}
            ),
            type_breakdown AS (
                SELECT
                    security_id,
                    GROUP_CONCAT(type_label, ', ') AS fund_type_breakdown
                FROM (
                    SELECT
                        security_id,
                        fund_type || ': ' || COUNT(DISTINCT fund_id) AS type_label
                    FROM qualified_buyers
                    GROUP BY security_id, fund_type
                    ORDER BY security_id, COUNT(DISTINCT fund_id) DESC, fund_type ASC
                )
                GROUP BY security_id
            )
            SELECT
                qb.cusip,
                qb.ticker,
                qb.company_name,
                qb.sector,
                COUNT(DISTINCT qb.fund_id) AS funds_buying,
                GROUP_CONCAT(qb.fund_name, ', ') AS funds,
                CAST(ROUND(SUM(qb.added_value_usd), 0) AS INTEGER) AS total_dollars_added,
                tb.fund_type_breakdown
            FROM (SELECT * FROM qualified_buyers ORDER BY fund_name) qb
            JOIN type_breakdown tb ON qb.security_id = tb.security_id
            GROUP BY qb.security_id, qb.cusip, qb.ticker, qb.company_name, qb.sector, tb.fund_type_breakdown
            HAVING COUNT(DISTINCT qb.fund_id) >= ?
            ORDER BY funds_buying DESC, total_dollars_added DESC
        """
        return pd.read_sql_query(query, conn, params=tuple(params))


def get_etf_convergence_signals(
    period: str,
    min_funds: int = 3,
    min_pct_increase: float = 0.10,
    min_added_value: int = 1_000_000,
) -> pd.DataFrame:
    """
    Returns ETFs and index trusts accumulated by min_funds or more institutions in the given period
    using the same buyer criteria (>=10% share increase or NEW, >=$1M added, excluding options).
    """
    with get_connection() as conn:
        query = f"""
            WITH prior_period AS (
                SELECT MAX(period) AS prev_period
                FROM Fact_Holdings
                WHERE period < ?
            ),
            qualified_buyers AS (
                SELECT
                    h.security_id,
                    s.cusip,
                    s.ticker,
                    s.company_name,
                    s.security_class,
                    f.fund_id,
                    f.name AS fund_name,
                    f.fund_type,
                    (h.shares - COALESCE(prev.shares, 0)) * (CAST(h.value_usd AS REAL) / h.shares) AS added_value_usd
                FROM Fact_Holdings h
                JOIN Dim_Security s ON h.security_id = s.security_id
                JOIN Dim_Fund f ON h.fund_id = f.fund_id
                LEFT JOIN Fact_Holdings prev
                    ON prev.fund_id = h.fund_id
                   AND prev.security_id = h.security_id
                   AND COALESCE(prev.put_call, '') = COALESCE(h.put_call, '')
                   AND prev.period = (SELECT prev_period FROM prior_period)
                   AND prev.value_usd > 0
                WHERE h.period = ?
                  AND (h.put_call IS NULL OR h.put_call = '')
                  AND h.value_usd > 0
                  AND h.shares > 0
                  AND (
                      h.qoq_change_flag = 'NEW'
                      OR (prev.shares > 0 AND (h.shares - prev.shares) * 1.0 / prev.shares >= ?)
                  )
                  AND ((h.shares - COALESCE(prev.shares, 0)) * (CAST(h.value_usd AS REAL) / h.shares)) >= ?
                  AND {ETF_SQL_CONDITION}
            ),
            type_breakdown AS (
                SELECT
                    security_id,
                    GROUP_CONCAT(type_label, ', ') AS fund_type_breakdown
                FROM (
                    SELECT
                        security_id,
                        fund_type || ': ' || COUNT(DISTINCT fund_id) AS type_label
                    FROM qualified_buyers
                    GROUP BY security_id, fund_type
                    ORDER BY security_id, COUNT(DISTINCT fund_id) DESC, fund_type ASC
                )
                GROUP BY security_id
            )
            SELECT
                qb.cusip,
                qb.ticker,
                qb.company_name,
                qb.security_class,
                COUNT(DISTINCT qb.fund_id) AS funds_buying,
                GROUP_CONCAT(qb.fund_name, ', ') AS funds,
                CAST(ROUND(SUM(qb.added_value_usd), 0) AS INTEGER) AS total_dollars_added,
                tb.fund_type_breakdown
            FROM (SELECT * FROM qualified_buyers ORDER BY fund_name) qb
            JOIN type_breakdown tb ON qb.security_id = tb.security_id
            GROUP BY qb.security_id, qb.cusip, qb.ticker, qb.company_name, qb.security_class, tb.fund_type_breakdown
            HAVING COUNT(DISTINCT qb.fund_id) >= ?
            ORDER BY funds_buying DESC, total_dollars_added DESC
        """
        return pd.read_sql_query(
            query,
            conn,
            params=(period, period, min_pct_increase, min_added_value, min_funds),
        )


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
            f.fund_type,
            s.cusip,
            s.ticker,
            s.company_name,
            s.sector,
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


def get_qoq_exited_positions(period: str) -> pd.DataFrame:
    """
    Returns all holdings where qoq_change_flag = 'EXITED' for the given period,
    joined with prior-quarter shares and dollar value.

    Args:
        period (str): The reporting period (e.g., '2026-Q2').

    Returns:
        pd.DataFrame: Exited positions ranked by prior-quarter value_usd descending.
    """
    query = """
        WITH prior_period AS (
            SELECT MAX(period) AS prev_period
            FROM Fact_Holdings
            WHERE period < ?
        )
        SELECT
            f.name AS fund_name,
            f.fund_type,
            s.cusip,
            s.ticker,
            s.company_name,
            s.sector,
            h.put_call,
            prev.value_usd AS prior_value_usd,
            prev.shares AS prior_shares,
            prev.pct_of_portfolio AS prior_pct_of_portfolio
        FROM Fact_Holdings h
        JOIN Dim_Security s ON h.security_id = s.security_id
        JOIN Dim_Fund f ON h.fund_id = f.fund_id
        LEFT JOIN Fact_Holdings prev
            ON prev.fund_id = h.fund_id
           AND prev.security_id = h.security_id
           AND COALESCE(prev.put_call, '') = COALESCE(h.put_call, '')
           AND prev.period = (SELECT prev_period FROM prior_period)
        WHERE h.period = ?
          AND h.qoq_change_flag = 'EXITED'
        ORDER BY prev.value_usd DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=(period, period))


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
            s.sector,
            SUM(h.value_usd) AS total_aum,
            COUNT(DISTINCT h.fund_id) AS funds_holding,
            GROUP_CONCAT(DISTINCT f.name) AS holding_funds
        FROM Fact_Holdings h
        JOIN Dim_Security s ON h.security_id = s.security_id
        JOIN Dim_Fund f ON h.fund_id = f.fund_id
        WHERE h.period = ?
          AND (h.put_call IS NULL OR h.put_call = '')
          AND (h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED')
          AND h.value_usd > 0
        GROUP BY s.security_id, s.cusip, s.ticker, s.company_name, s.sector
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
            s.sector,
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


def get_aum_by_period() -> pd.DataFrame:
    """
    Computes total institutional AUM per period with and without option positions.

    Returns:
        pd.DataFrame: Period-level AUM summary with and without options.
    """
    query = """
        SELECT
            h.period,
            COUNT(DISTINCT h.fund_id) AS fund_count,
            SUM(CASE WHEN h.value_usd > 0 THEN h.value_usd ELSE 0 END) AS aum_with_options_usd,
            SUM(CASE WHEN h.value_usd > 0 AND (h.put_call IS NULL OR h.put_call = '') THEN h.value_usd ELSE 0 END) AS aum_without_options_usd,
            SUM(CASE WHEN h.value_usd > 0 AND h.put_call IN ('Put', 'Call') THEN h.value_usd ELSE 0 END) AS options_aum_usd,
            ROUND(
                SUM(CASE WHEN h.value_usd > 0 AND h.put_call IN ('Put', 'Call') THEN h.value_usd ELSE 0 END) * 100.0
                / SUM(CASE WHEN h.value_usd > 0 THEN h.value_usd ELSE 0 END),
                2
            ) AS options_pct_of_total
        FROM Fact_Holdings h
        GROUP BY h.period
        ORDER BY h.period
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


def get_fund_summary() -> pd.DataFrame:
    """
    Produces a fund-by-period summary table for Power BI (output/fund_summary.csv),
    including total AUM with and without options, active position counts, QoQ activity breakdown,
    and top-10 concentration percentage.

    Returns:
        pd.DataFrame: Fund summary per period.
    """
    query = """
        WITH ranked AS (
            SELECT
                h.fund_id,
                h.period,
                h.value_usd,
                h.pct_of_portfolio,
                ROW_NUMBER() OVER (PARTITION BY h.fund_id, h.period ORDER BY h.value_usd DESC) AS rn
            FROM Fact_Holdings h
            WHERE h.value_usd > 0
              AND (h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED')
        ),
        top10 AS (
            SELECT
                fund_id,
                period,
                ROUND(SUM(pct_of_portfolio), 2) AS top_10_concentration_pct
            FROM ranked
            WHERE rn <= 10
            GROUP BY fund_id, period
        )
        SELECT
            f.name AS fund_name,
            f.cik,
            f.fund_type,
            h.period,
            SUM(CASE WHEN h.value_usd > 0 THEN 1 ELSE 0 END) AS active_positions,
            SUM(CASE WHEN h.value_usd > 0 AND (h.put_call IS NULL OR h.put_call = '') THEN 1 ELSE 0 END) AS equity_positions,
            SUM(CASE WHEN h.value_usd > 0 AND h.put_call IN ('Put', 'Call') THEN 1 ELSE 0 END) AS option_positions,
            SUM(CASE WHEN h.value_usd > 0 THEN h.value_usd ELSE 0 END) AS total_aum_with_options_usd,
            SUM(CASE WHEN h.value_usd > 0 AND (h.put_call IS NULL OR h.put_call = '') THEN h.value_usd ELSE 0 END) AS equity_aum_without_options_usd,
            t.top_10_concentration_pct,
            SUM(CASE WHEN h.qoq_change_flag = 'NEW' THEN 1 ELSE 0 END) AS new_positions_count,
            SUM(CASE WHEN h.qoq_change_flag = 'INCREASED' THEN 1 ELSE 0 END) AS increased_positions_count,
            SUM(CASE WHEN h.qoq_change_flag = 'DECREASED' THEN 1 ELSE 0 END) AS decreased_positions_count,
            SUM(CASE WHEN h.qoq_change_flag = 'UNCHANGED' THEN 1 ELSE 0 END) AS unchanged_positions_count,
            SUM(CASE WHEN h.qoq_change_flag = 'EXITED' THEN 1 ELSE 0 END) AS exited_positions_count
        FROM Fact_Holdings h
        JOIN Dim_Fund f ON h.fund_id = f.fund_id
        LEFT JOIN top10 t ON t.fund_id = h.fund_id AND t.period = h.period
        GROUP BY f.fund_id, f.name, f.cik, f.fund_type, h.period, t.top_10_concentration_pct
        ORDER BY h.period, total_aum_with_options_usd DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


def get_sector_by_period() -> pd.DataFrame:
    """
    Produces a sector-by-period breakdown of institutional AUM (output/sector_by_period.csv),
    showing both common-equity AUM (excluding options) and total AUM (including options).

    Returns:
        pd.DataFrame: Sector AUM and portfolio share per period.
    """
    query = """
        WITH period_totals AS (
            SELECT
                period,
                SUM(CASE WHEN value_usd > 0 AND (put_call IS NULL OR put_call = '') THEN value_usd ELSE 0 END) AS period_equity_aum,
                SUM(CASE WHEN value_usd > 0 THEN value_usd ELSE 0 END) AS period_total_aum
            FROM Fact_Holdings
            GROUP BY period
        )
        SELECT
            h.period,
            s.sector,
            SUM(CASE WHEN h.value_usd > 0 AND (h.put_call IS NULL OR h.put_call = '') THEN 1 ELSE 0 END) AS equity_positions,
            COUNT(DISTINCT CASE WHEN h.value_usd > 0 AND (h.put_call IS NULL OR h.put_call = '') THEN h.fund_id END) AS funds_holding_equity,
            SUM(CASE WHEN h.value_usd > 0 AND (h.put_call IS NULL OR h.put_call = '') THEN h.value_usd ELSE 0 END) AS equity_aum_usd,
            ROUND(
                SUM(CASE WHEN h.value_usd > 0 AND (h.put_call IS NULL OR h.put_call = '') THEN h.value_usd ELSE 0 END) * 100.0
                / pt.period_equity_aum,
                2
            ) AS pct_of_equity_aum,
            SUM(CASE WHEN h.value_usd > 0 THEN h.value_usd ELSE 0 END) AS total_aum_with_options_usd,
            ROUND(
                SUM(CASE WHEN h.value_usd > 0 THEN h.value_usd ELSE 0 END) * 100.0
                / pt.period_total_aum,
                2
            ) AS pct_of_total_aum
        FROM Fact_Holdings h
        JOIN Dim_Security s ON h.security_id = s.security_id
        JOIN period_totals pt ON pt.period = h.period
        WHERE h.value_usd > 0
          AND (h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED')
        GROUP BY h.period, s.sector, pt.period_equity_aum, pt.period_total_aum
        ORDER BY h.period ASC, equity_aum_usd DESC
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


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
    df_signals = get_convergence_signals("2026-Q2", min_funds=4)
    print(df_signals)



