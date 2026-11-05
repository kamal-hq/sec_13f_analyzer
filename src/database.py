"""
Handles all SQLite database operations including schema creation and data insertion.
"""

import logging
import os
import sqlite3
import pandas as pd
from config import DB_PATH, FUND_TYPES, TARGET_FUNDS

logger = logging.getLogger(__name__)

CIK_TO_FUND_NAME: dict[str, str] = {cik: name for name, cik in TARGET_FUNDS.items()}


def get_connection() -> sqlite3.Connection:
    """
    Returns a SQLite connection to DB_PATH with row_factory set to sqlite3.Row.
    
    Returns:
        sqlite3.Connection: Database connection object.
    """
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema() -> None:
    """
    Creates all three tables (Dim_Fund, Dim_Security, Fact_Holdings) and View_Exited_Positions if they do not exist.
    
    SQL Schema:
    ```sql
    CREATE TABLE Dim_Fund (
        fund_id INTEGER PRIMARY KEY AUTOINCREMENT,
        cik TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        fund_type TEXT
    );
    
    CREATE TABLE Dim_Security (
        security_id INTEGER PRIMARY KEY AUTOINCREMENT,
        cusip TEXT UNIQUE NOT NULL,
        ticker TEXT,
        company_name TEXT,
        security_class TEXT,
        sector TEXT
    );
    
    CREATE TABLE Fact_Holdings (
        holding_id INTEGER PRIMARY KEY AUTOINCREMENT,
        fund_id INTEGER NOT NULL REFERENCES Dim_Fund(fund_id),
        security_id INTEGER NOT NULL REFERENCES Dim_Security(security_id),
        period TEXT NOT NULL,
        put_call TEXT,
        value_usd INTEGER,
        shares INTEGER,
        pct_of_portfolio REAL,
        qoq_change_flag TEXT CHECK(qoq_change_flag IN ('NEW','INCREASED','DECREASED','EXITED','UNCHANGED'))
    );
    ```
    """
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS Dim_Fund (
                fund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cik TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                fund_type TEXT
            );

            CREATE TABLE IF NOT EXISTS Dim_Security (
                security_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cusip TEXT UNIQUE NOT NULL,
                ticker TEXT,
                company_name TEXT,
                security_class TEXT,
                sector TEXT
            );

            CREATE TABLE IF NOT EXISTS Fact_Holdings (
                holding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_id INTEGER NOT NULL REFERENCES Dim_Fund(fund_id),
                security_id INTEGER NOT NULL REFERENCES Dim_Security(security_id),
                period TEXT NOT NULL,
                put_call TEXT,
                value_usd INTEGER,
                shares INTEGER,
                pct_of_portfolio REAL,
                qoq_change_flag TEXT CHECK(qoq_change_flag IN ('NEW','INCREASED','DECREASED','EXITED','UNCHANGED'))
            );

            CREATE VIEW IF NOT EXISTS View_Exited_Positions AS
            SELECT
                h.holding_id,
                f.fund_id,
                f.name AS fund_name,
                s.security_id,
                s.cusip,
                s.ticker,
                s.company_name,
                h.period,
                h.put_call
            FROM Fact_Holdings h
            JOIN Dim_Fund f ON h.fund_id = f.fund_id
            JOIN Dim_Security s ON h.security_id = s.security_id
            WHERE h.qoq_change_flag = 'EXITED';

            CREATE INDEX IF NOT EXISTS idx_fact_fund_period ON Fact_Holdings(fund_id, period);
            CREATE INDEX IF NOT EXISTS idx_fact_period_flag ON Fact_Holdings(period, qoq_change_flag);
            CREATE INDEX IF NOT EXISTS idx_fact_security ON Fact_Holdings(security_id);
            """
        )
        # Ensure security_class column exists if migrating an older Dim_Security table
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(Dim_Security)").fetchall()]
        if "security_class" not in cols:
            conn.execute("ALTER TABLE Dim_Security ADD COLUMN security_class TEXT")
    logger.info("Star schema verified at %s", DB_PATH)


def insert_fund(
    cik: str,
    name: str,
    fund_type: str = "Institutional Investment Manager",
    _conn: sqlite3.Connection | None = None,
) -> int:
    """
    Inserts or ignores a fund record.
    
    Args:
        cik (str): Central Index Key.
        name (str): Fund name.
        fund_type (str): Fund type.
        
    Returns:
        int: The fund_id of the inserted or existing record.
    """
    own_conn = _conn is None
    conn = _conn if _conn is not None else get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO Dim_Fund (cik, name, fund_type) VALUES (?, ?, ?)",
            (cik, name, fund_type),
        )
        conn.execute(
            "UPDATE Dim_Fund SET name = ?, fund_type = ? WHERE cik = ?",
            (name, fund_type, cik),
        )
        row = conn.execute("SELECT fund_id FROM Dim_Fund WHERE cik = ?", (cik,)).fetchone()
        if own_conn:
            conn.commit()
        return int(row["fund_id"])
    finally:
        if own_conn:
            conn.close()


def insert_security(
    cusip: str,
    ticker: str | None,
    company_name: str | None,
    sector: str | None,
    security_class: str | None = None,
    _conn: sqlite3.Connection | None = None,
) -> int:
    """
    Inserts or updates a security record with its security_class (titleOfClass) and SIC-mapped sector.
    
    Args:
        cusip (str): CUSIP identifier.
        ticker (str): Ticker symbol.
        company_name (str): Issuer name.
        sector (str): Broad sector name mapped from SEC SIC code ('Unknown' fallback).
        security_class (str | None): 13F titleOfClass (e.g., COM, CL A).
        
    Returns:
        int: The security_id of the inserted or existing record.
    """
    own_conn = _conn is None
    conn = _conn if _conn is not None else get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO Dim_Security (cusip, ticker, company_name, security_class, sector)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cusip, ticker, company_name, security_class, sector or "Unknown"),
        )
        conn.execute(
            """
            UPDATE Dim_Security
            SET ticker = COALESCE(?, ticker),
                company_name = COALESCE(?, company_name),
                security_class = COALESCE(?, security_class),
                sector = COALESCE(?, sector)
            WHERE cusip = ?
            """,
            (ticker, company_name, security_class, sector, cusip),
        )
        row = conn.execute("SELECT security_id FROM Dim_Security WHERE cusip = ?", (cusip,)).fetchone()
        if own_conn:
            conn.commit()
        return int(row["security_id"])
    finally:
        if own_conn:
            conn.close()



def insert_holding(
    fund_id: int,
    security_id: int,
    period: str,
    value_usd: int,
    shares: int,
    pct_of_portfolio: float,
    qoq_change_flag: str | None,
    put_call: str | None = None,
    _conn: sqlite3.Connection | None = None,
) -> None:
    """
    Inserts a single holding record into Fact_Holdings.
    
    Args:
        fund_id (int): Fund ID.
        security_id (int): Security ID.
        period (str): Reporting period (e.g., 2026-Q2).
        value_usd (int): Value in USD.
        shares (int): Number of shares.
        pct_of_portfolio (float): Percentage of portfolio.
        qoq_change_flag (str | None): QoQ change flag (None/NULL for earliest period).
        put_call (str | None): Optional option indicator ('Put' or 'Call', None for equity).
    """
    own_conn = _conn is None
    conn = _conn if _conn is not None else get_connection()
    try:
        conn.execute(
            """
            INSERT INTO Fact_Holdings (
                fund_id, security_id, period, put_call, value_usd, shares, pct_of_portfolio, qoq_change_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fund_id, security_id, period, put_call, value_usd, shares, pct_of_portfolio, qoq_change_flag),
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def _compute_portfolio_and_qoq_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes pct_of_portfolio per (fund_cik, period) and qoq_change_flag
    (NULL for earliest period; NEW, INCREASED, DECREASED, EXITED, UNCHANGED for subsequent periods).
    """
    work = df.copy()
    if "value_usd" not in work.columns and "value" in work.columns:
        work["value_usd"] = work["value"]

    # Normalize put_call so None and empty string match consistently across quarters
    work["put_call"] = work["put_call"].apply(
        lambda x: str(x).strip() if pd.notna(x) and str(x).strip() != "" else None
    )

    # Compute pct_of_portfolio per fund per period
    period_totals = work.groupby(["fund_cik", "period"])["value_usd"].transform("sum")
    work["pct_of_portfolio"] = (
        (work["value_usd"] / period_totals.replace(0, pd.NA)) * 100.0
    ).fillna(0.0).round(6)

    result_frames: list[pd.DataFrame] = []

    for fund_cik, fund_df in work.groupby("fund_cik", sort=False):
        periods = sorted(fund_df["period"].unique())
        prev_lookup: dict[tuple[str, str | None], dict] | None = None

        for period in periods:
            curr_df = fund_df[fund_df["period"] == period].copy()
            curr_lookup: dict[tuple[str, str | None], dict] = {}
            flags: list[str | None] = []

            for row in curr_df.to_dict("records"):
                key = (row["cusip"], row["put_call"])
                curr_lookup[key] = row
                if prev_lookup is None:
                    # Earliest period has no prior quarter to compare against -> NULL in SQLite
                    flags.append(None)
                elif key not in prev_lookup or prev_lookup[key]["shares"] == 0:
                    flags.append("NEW")
                else:
                    prev_shares = prev_lookup[key]["shares"]
                    if row["shares"] > prev_shares:
                        flags.append("INCREASED")
                    elif row["shares"] < prev_shares:
                        flags.append("DECREASED")
                    else:
                        flags.append("UNCHANGED")

            curr_df["qoq_change_flag"] = flags
            result_frames.append(curr_df)

            # Generate EXITED records with value_usd=0 and shares=0 for positions present in prior period but absent now
            if prev_lookup is not None:
                exited_rows: list[dict] = []
                for key, prev_row in prev_lookup.items():
                    if key not in curr_lookup and prev_row["shares"] > 0:
                        exited = dict(prev_row)
                        exited["period"] = period
                        exited["value"] = 0
                        exited["value_usd"] = 0
                        exited["shares"] = 0
                        exited["pct_of_portfolio"] = 0.0
                        exited["qoq_change_flag"] = "EXITED"
                        exited_rows.append(exited)
                if exited_rows:
                    result_frames.append(pd.DataFrame(exited_rows))

            prev_lookup = curr_lookup

    return pd.concat(result_frames, ignore_index=True)


def bulk_insert_holdings(df: pd.DataFrame) -> None:
    """
    Takes the parsed and mapped DataFrame and runs the full insert pipeline
    calling the individual insert functions for funds, securities, and holdings.
    
    Args:
        df (pd.DataFrame): The transformed DataFrame ready for insertion.
    """
    if df.empty:
        logger.warning("bulk_insert_holdings received an empty DataFrame; nothing to insert.")
        return

    create_schema()
    enriched_df = _compute_portfolio_and_qoq_metrics(df)

    conn = get_connection()
    try:
        with conn:
            # 1. Insert funds and cache fund_id by cik
            fund_ids: dict[str, int] = {}
            for fund_cik in enriched_df["fund_cik"].unique():
                fund_name = CIK_TO_FUND_NAME.get(fund_cik)
                if not fund_name and "fund_name" in enriched_df.columns:
                    sub = enriched_df.loc[enriched_df["fund_cik"] == fund_cik, "fund_name"].dropna()
                    fund_name = str(sub.iloc[0]) if not sub.empty else f"CIK {fund_cik}"
                fund_type = FUND_TYPES.get(fund_cik, "Hedge Fund")
                fund_ids[fund_cik] = insert_fund(fund_cik, fund_name or f"CIK {fund_cik}", fund_type, _conn=conn)

            # 2. Clear existing Fact_Holdings for the (fund_id, period) pairs being loaded for idempotency
            for (fund_cik, period), _ in enriched_df.groupby(["fund_cik", "period"]):
                conn.execute(
                    "DELETE FROM Fact_Holdings WHERE fund_id = ? AND period = ?",
                    (fund_ids[fund_cik], period),
                )

            # 3. Insert unique securities and cache security_id by cusip
            security_ids: dict[str, int] = {}
            sec_cols = [c for c in ["cusip", "ticker", "company_name", "issuer_name", "security_class", "title_of_class", "sector"] if c in enriched_df.columns]
            unique_sec_df = enriched_df[sec_cols].drop_duplicates(subset=["cusip"])
            for sec_row in unique_sec_df.to_dict("records"):
                cusip = sec_row["cusip"]
                ticker = sec_row.get("ticker")
                company_name = sec_row.get("company_name") or sec_row.get("issuer_name")
                security_class = sec_row.get("security_class") or sec_row.get("title_of_class")
                sector = sec_row.get("sector") or "Unknown"
                security_ids[cusip] = insert_security(
                    cusip=cusip,
                    ticker=ticker if pd.notna(ticker) else None,
                    company_name=company_name if pd.notna(company_name) else None,
                    sector=sector if pd.notna(sector) else "Unknown",
                    security_class=security_class if pd.notna(security_class) else None,
                    _conn=conn,
                )


            # 4. Insert all holdings into Fact_Holdings
            for row in enriched_df.to_dict("records"):
                put_call_val = row.get("put_call")
                put_call_clean = str(put_call_val) if pd.notna(put_call_val) and put_call_val is not None else None
                flag_val = row.get("qoq_change_flag")
                flag_clean = str(flag_val) if pd.notna(flag_val) and flag_val is not None else None
                insert_holding(
                    fund_id=fund_ids[row["fund_cik"]],
                    security_id=security_ids[row["cusip"]],
                    period=str(row["period"]),
                    value_usd=int(row["value_usd"]),
                    shares=int(row["shares"]),
                    pct_of_portfolio=float(row["pct_of_portfolio"]),
                    qoq_change_flag=flag_clean,
                    put_call=put_call_clean,
                    _conn=conn,
                )

            # Remove any orphan securities from superseded filings
            conn.execute(
                "DELETE FROM Dim_Security WHERE security_id NOT IN (SELECT DISTINCT security_id FROM Fact_Holdings)"
            )

        logger.info(

            "Loaded %d funds, %d securities, and %d holding records into %s",
            len(fund_ids),
            len(security_ids),
            len(enriched_df),
            DB_PATH,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    create_schema()
    logging.info("Database schema confirmed/created.")

