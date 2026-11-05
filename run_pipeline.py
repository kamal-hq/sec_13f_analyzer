"""
End-to-end SEC 13F pipeline runner: Parse -> Map -> Load -> Summary.
"""

import logging
import os
import pandas as pd
from src.analysis import get_convergence_signals, get_fund_concentration
from src.cusip_mapper import map_cusips
from src.database import bulk_insert_holdings, create_schema, get_connection
from src.parse_holdings import parse_all_raw_files, validate_parsed_data

logger = logging.getLogger(__name__)


def run_pipeline() -> pd.DataFrame:
    """
    Executes the full 13F data pipeline:
    1. Parse and aggregate raw 13F XML files from data/raw/
    2. Map unique CUSIPs to tickers and security names via OpenFIGI + local cache
    3. Load funds, securities, and holdings (with pct_of_portfolio and qoq_change_flag) into SQLite
    
    Returns:
        pd.DataFrame: The parsed and mapped DataFrame loaded into the database.
    """
    logger.info("Step 1/3: Parsing and aggregating raw 13F XML files...")
    df = parse_all_raw_files()
    df = validate_parsed_data(df)

    logger.info("Step 2/3: Mapping %d unique CUSIPs...", df["cusip"].nunique())
    unique_cusips = df["cusip"].unique().tolist()
    cusip_map = map_cusips(unique_cusips)

    df["ticker"] = df["cusip"].map(lambda c: cusip_map.get(c, {}).get("ticker"))
    # Prefer OpenFIGI canonical company name when available, falling back to 13F XML issuer_name
    df["company_name"] = df.apply(
        lambda r: cusip_map.get(r["cusip"], {}).get("name") or r["issuer_name"],
        axis=1,
    )
    df["sector"] = df.apply(
        lambda r: cusip_map.get(r["cusip"], {}).get("security_type") or r["title_of_class"],
        axis=1,
    )

    os.makedirs(os.path.join("data", "processed"), exist_ok=True)
    processed_path = os.path.join("data", "processed", "holdings_mapped.csv")
    df.to_csv(processed_path, index=False)
    logger.info("Saved mapped holdings to %s", processed_path)

    logger.info("Step 3/3: Creating database schema and loading star schema tables...")
    create_schema()
    bulk_insert_holdings(df)

    with get_connection() as conn:
        for table in ("Dim_Fund", "Dim_Security", "Fact_Holdings"):
            count = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()["cnt"]
            logger.info("Table %s row count: %d", table, count)

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_pipeline()

    print("\n=== Table Row Counts ===")
    with get_connection() as conn:
        for tbl in ("Dim_Fund", "Dim_Security", "Fact_Holdings"):
            cnt = conn.execute(f"SELECT COUNT(*) AS cnt FROM {tbl}").fetchone()["cnt"]
            print(f"{tbl}: {cnt:,}")

        print("\n=== Funds per Period ===")
        period_df = pd.read_sql_query(
            """
            SELECT
                h.period,
                COUNT(DISTINCT h.fund_id) AS fund_count,
                COUNT(*) AS total_rows,
                SUM(CASE WHEN h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED' THEN 1 ELSE 0 END) AS active_rows,
                SUM(CASE WHEN h.qoq_change_flag = 'EXITED' THEN 1 ELSE 0 END) AS exited_rows,
                SUM(h.value_usd) AS total_aum_usd
            FROM Fact_Holdings h
            GROUP BY h.period
            ORDER BY h.period

            """,
            conn,
        )
        print(period_df.to_string(index=False))

    print("\n=== Top 10 Holdings for Berkshire Hathaway (2026-Q2) ===")
    top_berk = get_fund_concentration("Berkshire Hathaway", "2026-Q2")
    print(top_berk.to_string(index=False))

    print("\n=== Smart Money Convergence Signals (2026-Q2, Top 25) ===")
    signals = get_convergence_signals("2026-Q2")
    print(f"Total convergence signal stocks (3+ funds buying in 2026-Q2): {len(signals)}")
    print(signals.head(25).to_string(index=False))

