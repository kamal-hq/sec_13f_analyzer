"""
Handles all SQLite database operations including schema creation and data insertion.
"""

import json
import logging
import os
import sqlite3
import pandas as pd
from config import COMMON_SPLIT_FACTORS, DB_PATH, FUND_TYPES, SPLIT_OVERRIDES, TARGET_FUNDS

logger = logging.getLogger(__name__)

CIK_TO_FUND_NAME: dict[str, str] = {cik: name for name, cik in TARGET_FUNDS.items()}
SPLIT_CACHE_PATH = os.path.join("data", "mappings", "split_cache.json")


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
                qoq_change_flag TEXT CHECK(qoq_change_flag IN ('NEW','INCREASED','DECREASED','EXITED','UNCHANGED')),
                is_new_listing INTEGER
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
        # Ensure security_class and is_new_listing columns exist if migrating an older database
        sec_cols = [r["name"] for r in conn.execute("PRAGMA table_info(Dim_Security)").fetchall()]
        if "security_class" not in sec_cols:
            conn.execute("ALTER TABLE Dim_Security ADD COLUMN security_class TEXT")
        fact_cols = [r["name"] for r in conn.execute("PRAGMA table_info(Fact_Holdings)").fetchall()]
        if "is_new_listing" not in fact_cols:
            conn.execute("ALTER TABLE Fact_Holdings ADD COLUMN is_new_listing INTEGER")
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
    is_new_listing: int | None = None,
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
        is_new_listing (int | None): 1 if no fund held the security in the prior period, 0 otherwise, None for earliest period.
    """
    own_conn = _conn is None
    conn = _conn if _conn is not None else get_connection()
    try:
        conn.execute(
            """
            INSERT INTO Fact_Holdings (
                fund_id, security_id, period, put_call, value_usd, shares, pct_of_portfolio, qoq_change_flag, is_new_listing
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fund_id,
                security_id,
                period,
                put_call,
                value_usd,
                shares,
                pct_of_portfolio,
                qoq_change_flag,
                is_new_listing,
            ),
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def _load_split_cache() -> dict[str, dict]:
    """Loads cached yfinance split confirmations from data/mappings/split_cache.json."""
    if os.path.exists(SPLIT_CACHE_PATH):
        try:
            with open(SPLIT_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to read split cache %s: %s", SPLIT_CACHE_PATH, exc)
    return {}


def _save_split_cache(cache: dict[str, dict]) -> None:
    """Persists yfinance split confirmations to data/mappings/split_cache.json."""
    os.makedirs(os.path.dirname(SPLIT_CACHE_PATH), exist_ok=True)
    with open(SPLIT_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def _confirm_split_with_yfinance(ticker: str | None, expected_factor: float) -> tuple[str, str | None]:
    """
    Checks yfinance split history for `ticker` between 2026-Q1 and 2026-Q2 period-ends
    (2026-03-25 through 2026-07-05) to confirm an auto-detected stock split.
    Caches confirmations in data/mappings/split_cache.json and falls back to the cache
    (logging when the cache is used) if the network call fails.
    Returns (confirmation_status, split_date) where confirmation_status is 'CONFIRMED' or 'UNCONFIRMED'.
    """
    if not ticker or pd.isna(ticker) or str(ticker).strip() in ("", "None"):
        return "UNCONFIRMED", None

    clean_ticker = str(ticker).strip().upper()
    cache = _load_split_cache()

    try:
        import yfinance as yf

        splits = yf.Ticker(clean_ticker).splits
        # If yfinance swallowed a network error and returned empty for a previously confirmed split, use cache
        if (splits is None or len(splits) == 0) and clean_ticker in cache and cache[clean_ticker].get("confirmation_status") == "CONFIRMED":
            entry = cache[clean_ticker]
            logger.info(
                "Using cached split confirmation for %s from %s (%s on %s)",
                clean_ticker,
                SPLIT_CACHE_PATH,
                entry.get("confirmation_status"),
                entry.get("split_date"),
            )
            return str(entry["confirmation_status"]), entry.get("split_date")

        status = "UNCONFIRMED"
        split_date: str | None = None
        if splits is not None and len(splits) > 0:
            for dt, ratio in splits.items():
                dt_str = str(dt)[:10]
                if "2026-03-25" <= dt_str <= "2026-07-05":
                    r = float(ratio)
                    if r > 0 and abs(r - expected_factor) / expected_factor <= 0.10:
                        status = "CONFIRMED"
                        split_date = dt_str
                        break

        cache[clean_ticker] = {
            "confirmation_status": status,
            "expected_factor": float(expected_factor),
            "split_date": split_date,
        }
        _save_split_cache(cache)
        return status, split_date
    except Exception as exc:
        if clean_ticker in cache:
            entry = cache[clean_ticker]
            logger.info(
                "yfinance network call failed for %s (%s); using cached split confirmation from %s (%s)",
                clean_ticker,
                exc,
                SPLIT_CACHE_PATH,
                entry.get("confirmation_status"),
            )
            return str(entry.get("confirmation_status", "UNCONFIRMED")), entry.get("split_date")
        logger.warning("yfinance split check failed for %s and no cache entry found: %s", clean_ticker, exc)
        return "UNCONFIRMED", None


def detect_splits(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detects stock splits (forward and reverse) between the prior period and current period.
    For each CUSIP, computes implied price per share (value/shares) per period using the median
    across funds. If the Q1/Q2 price ratio is within 5% of a common split factor
    (2, 3, 4, 5, 8, 10, 15, 20, 25, 30) and median shares move inversely in proportion to the split,
    flags a candidate split and confirms it against yfinance split history.
    Ground-truth entries in SPLIT_OVERRIDES are always marked CONFIRMED.

    Args:
        df (pd.DataFrame): Holdings DataFrame containing cusip, period, value/value_usd, shares, put_call.

    Returns:
        pd.DataFrame: Detected splits with columns:
            cusip, ticker, company_name, split_factor, split_type, detection_source,
            confirmation_status, split_date,
            q1_median_price, q2_median_price, price_ratio_q1_q2, q1_median_shares, q2_median_shares, share_ratio_q2_q1.
    """
    work = df.copy()
    val_col = "value_usd" if "value_usd" in work.columns else "value"
    name_col = "company_name" if "company_name" in work.columns else "issuer_name"
    if "ticker" not in work.columns:
        work["ticker"] = None

    # Exclude options and zero-value/zero-share rows when computing implied equity share prices
    eq = work[
        (work["put_call"].isna() | (work["put_call"] == ""))
        & (work[val_col] > 0)
        & (work["shares"] > 0)
    ].copy()

    periods = sorted(eq["period"].unique())
    if len(periods) < 2:
        return pd.DataFrame()

    p_prev, p_curr = periods[0], periods[-1]
    eq["implied_price"] = eq[val_col] / eq["shares"]

    meta = (
        eq.groupby("cusip", as_index=False)
        .agg(ticker=("ticker", "first"), company_name=(name_col, "first"))
        .set_index("cusip")
    )

    stats = (
        eq.groupby(["cusip", "period"])
        .agg(med_price=("implied_price", "median"), med_shares=("shares", "median"))
        .unstack("period")
    )
    if p_prev not in stats["med_price"].columns or p_curr not in stats["med_price"].columns:
        return pd.DataFrame()

    stats = stats.dropna(subset=[("med_price", p_prev), ("med_price", p_curr)])

    # Also compute matched-fund median share ratio (q2_shares / q1_shares) for funds holding in both periods
    q1_sh = eq[eq["period"] == p_prev].set_index(["cusip", "fund_cik"])["shares"]
    q2_sh = eq[eq["period"] == p_curr].set_index(["cusip", "fund_cik"])["shares"]
    matched_sr = (q2_sh / q1_sh).dropna().groupby("cusip").median()

    override_dates = {"482480100": "2026-06-11", "09857L108": "2026-04-02"}

    detected_rows: list[dict] = []
    for cusip, row in stats.iterrows():
        p1 = float(row[("med_price", p_prev)])
        p2 = float(row[("med_price", p_curr)])
        s1 = float(row[("med_shares", p_prev)])
        s2 = float(row[("med_shares", p_curr)])
        if p2 <= 0 or s1 <= 0:
            continue

        pr = p1 / p2
        sr = s2 / s1
        msr = float(matched_sr.get(cusip, sr))

        ticker = meta.loc[cusip, "ticker"] if cusip in meta.index else None
        company = meta.loc[cusip, "company_name"] if cusip in meta.index else None

        if cusip in SPLIT_OVERRIDES:
            factor = float(SPLIT_OVERRIDES[cusip])
            split_label = f"{int(factor)}-for-1" if factor >= 1 else f"1-for-{int(round(1.0 / factor))}"
            detected_rows.append(
                {
                    "cusip": cusip,
                    "ticker": ticker,
                    "company_name": company,
                    "split_factor": factor,
                    "split_type": split_label,
                    "detection_source": "OVERRIDE",
                    "confirmation_status": "CONFIRMED",
                    "split_date": override_dates.get(cusip, "OVERRIDE"),
                    "q1_median_price": round(p1, 2),
                    "q2_median_price": round(p2, 2),
                    "price_ratio_q1_q2": round(pr, 3),
                    "q1_median_shares": int(round(s1)),
                    "q2_median_shares": int(round(s2)),
                    "share_ratio_q2_q1": round(sr, 3),
                }
            )
            continue

        for f in COMMON_SPLIT_FACTORS:
            # Forward split: Q1/Q2 price ratio within 5% of f, and median shares move inversely (~f)
            if abs(pr - f) / f <= 0.05 and sr > 1.0 and abs(sr - f) / f <= 0.30 and abs(msr - f) / f <= 0.25:
                status, s_date = _confirm_split_with_yfinance(ticker, float(f))
                detected_rows.append(
                    {
                        "cusip": cusip,
                        "ticker": ticker,
                        "company_name": company,
                        "split_factor": float(f),
                        "split_type": f"{f}-for-1",
                        "detection_source": "AUTO",
                        "confirmation_status": status,
                        "split_date": s_date,
                        "q1_median_price": round(p1, 2),
                        "q2_median_price": round(p2, 2),
                        "price_ratio_q1_q2": round(pr, 3),
                        "q1_median_shares": int(round(s1)),
                        "q2_median_shares": int(round(s2)),
                        "share_ratio_q2_q1": round(sr, 3),
                    }
                )
                break

            # Reverse split: Q2/Q1 price ratio within 5% of f, and median shares move inversely (~1/f)
            inv_pr = 1.0 / pr if pr > 0 else 0.0
            inv_sr = 1.0 / sr if sr > 0 else 0.0
            inv_msr = 1.0 / msr if msr > 0 else 0.0
            if abs(inv_pr - f) / f <= 0.05 and sr < 1.0 and abs(inv_sr - f) / f <= 0.30 and abs(inv_msr - f) / f <= 0.25:
                status, s_date = _confirm_split_with_yfinance(ticker, 1.0 / float(f))
                detected_rows.append(
                    {
                        "cusip": cusip,
                        "ticker": ticker,
                        "company_name": company,
                        "split_factor": 1.0 / float(f),
                        "split_type": f"1-for-{f} (Reverse)",
                        "detection_source": "AUTO",
                        "confirmation_status": status,
                        "split_date": s_date,
                        "q1_median_price": round(p1, 2),
                        "q2_median_price": round(p2, 2),
                        "price_ratio_q1_q2": round(pr, 3),
                        "q1_median_shares": int(round(s1)),
                        "q2_median_shares": int(round(s2)),
                        "share_ratio_q2_q1": round(sr, 3),
                    }
                )
                break

    out = pd.DataFrame(detected_rows)
    if not out.empty:
        out = out.sort_values(
            ["confirmation_status", "detection_source", "split_factor", "cusip"],
            ascending=[True, False, False, True],
        ).reset_index(drop=True)
    return out


def apply_split_adjustments(df: pd.DataFrame, splits_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Adjusts prior-period (Q1) share counts ONLY for confirmed splits (SPLIT_OVERRIDES plus
    auto-detected splits confirmed against yfinance split history). Unconfirmed auto-detected
    candidates are logged and NOT applied.
    """
    work = df.copy()
    if splits_df is None:
        splits_df = detect_splits(work)
    if splits_df.empty:
        return work

    periods = sorted(work["period"].unique())
    if len(periods) < 2:
        return work
    prior_period = periods[0]

    unconfirmed = splits_df[splits_df["confirmation_status"] != "CONFIRMED"]
    for _, u_row in unconfirmed.iterrows():
        logger.warning(
            "Skipping unconfirmed auto-detected split: CUSIP=%s, ticker=%s (%s), candidate=%s (Q1=$%.2f -> Q2=$%.2f)",
            u_row["cusip"],
            u_row["ticker"],
            u_row["company_name"],
            u_row["split_type"],
            u_row["q1_median_price"],
            u_row["q2_median_price"],
        )

    confirmed = splits_df[splits_df["confirmation_status"] == "CONFIRMED"]
    if confirmed.empty:
        return work

    split_map: dict[str, float] = dict(zip(confirmed["cusip"], confirmed["split_factor"]))
    mask = (work["period"] == prior_period) & (work["cusip"].isin(split_map)) & (work["shares"] > 0)

    if mask.any():
        factors = work.loc[mask, "cusip"].map(split_map)
        work.loc[mask, "shares"] = (
            (work.loc[mask, "shares"] * factors).round().astype("int64").clip(lower=1)
        )
        logger.info(
            "Applied confirmed stock split adjustments to %d prior-period (%s) holding rows across %d confirmed split CUSIPs (%d unconfirmed skipped).",
            int(mask.sum()),
            prior_period,
            len(split_map),
            len(unconfirmed),
        )
    return work


def _compute_portfolio_and_qoq_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies confirmed stock-split adjustments to prior-period shares, then computes pct_of_portfolio
    per (fund_cik, period), qoq_change_flag (NULL for earliest period; NEW, INCREASED,
    DECREASED, EXITED, UNCHANGED for subsequent periods) on split-adjusted shares, and
    is_new_listing (1 when NO fund held the security in the prior period, 0 otherwise, NULL for earliest period).
    """
    work = df.copy()
    if "value_usd" not in work.columns and "value" in work.columns:
        work["value_usd"] = work["value"]

    # Normalize put_call so None and empty string match consistently across quarters
    work["put_call"] = work["put_call"].apply(
        lambda x: str(x).strip() if pd.notna(x) and str(x).strip() != "" else None
    )

    # Adjust Q1 shares for confirmed stock splits before computing QoQ share changes and qoq_change_flag
    work = apply_split_adjustments(work)

    # Identify CUSIPs held by ANY fund in each period so we can flag is_new_listing
    all_periods = sorted(work["period"].unique())
    held_cusips_by_period: dict[str, set[str]] = {}
    for p in all_periods:
        sub_p = work[(work["period"] == p) & (work["value_usd"] > 0) & (work["shares"] > 0)]
        held_cusips_by_period[p] = set(sub_p["cusip"].unique())

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
            new_listing_flags: list[int | None] = []

            p_idx = all_periods.index(period)
            prior_held_cusips: set[str] | None = (
                held_cusips_by_period[all_periods[p_idx - 1]] if p_idx > 0 else None
            )

            for row in curr_df.to_dict("records"):
                key = (row["cusip"], row["put_call"])
                curr_lookup[key] = row
                if prior_held_cusips is None:
                    new_listing_flags.append(None)
                else:
                    new_listing_flags.append(0 if row["cusip"] in prior_held_cusips else 1)

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
            curr_df["is_new_listing"] = new_listing_flags
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
                        exited["is_new_listing"] = 0
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
                new_list_val = row.get("is_new_listing")
                new_list_clean = int(new_list_val) if pd.notna(new_list_val) and new_list_val is not None else None
                insert_holding(
                    fund_id=fund_ids[row["fund_cik"]],
                    security_id=security_ids[row["cusip"]],
                    period=str(row["period"]),
                    value_usd=int(row["value_usd"]),
                    shares=int(row["shares"]),
                    pct_of_portfolio=float(row["pct_of_portfolio"]),
                    qoq_change_flag=flag_clean,
                    put_call=put_call_clean,
                    is_new_listing=new_list_clean,
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


