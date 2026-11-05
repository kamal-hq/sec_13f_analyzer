"""
End-to-end SEC 13F pipeline runner: Parse -> Map -> Load -> Export CSVs -> Summary.
"""

import logging
import os
import pandas as pd
from src.analysis import (
    export_to_csv,
    get_aum_by_period,
    get_convergence_signals,
    get_fund_concentration,
    get_fund_summary,
    get_sector_by_period,
    get_top_holdings_by_aum,
)
from src.cusip_mapper import map_cusips, map_sectors
from src.database import bulk_insert_holdings, create_schema, get_connection
from src.parse_holdings import parse_all_raw_files, validate_parsed_data

logger = logging.getLogger(__name__)

DISCRETIONARY_FUND_TYPES = [
    "Conglomerate",
    "Public Pension Fund",
    "Sovereign Wealth Fund",
]


def run_pipeline() -> pd.DataFrame:
    """
    Executes the full 13F data pipeline:
    1. Parse and aggregate raw 13F XML files from data/raw/
    2. Map unique CUSIPs to tickers/names via OpenFIGI + cache, and map tickers to SIC sectors
    3. Load funds, securities, and holdings (with pct_of_portfolio and qoq_change_flag) into SQLite
    4. Export Power BI CSVs to output/
    
    Returns:
        pd.DataFrame: The parsed and mapped DataFrame loaded into the database.
    """
    logger.info("Step 1/4: Parsing and aggregating raw 13F XML files...")
    df = parse_all_raw_files()
    df = validate_parsed_data(df)

    logger.info("Step 2/4: Mapping %d unique CUSIPs and resolving SIC sectors...", df["cusip"].nunique())
    unique_cusips = df["cusip"].unique().tolist()
    cusip_map = map_cusips(unique_cusips)

    df["ticker"] = df["cusip"].map(lambda c: cusip_map.get(c, {}).get("ticker"))
    # Prefer OpenFIGI canonical company name when available, falling back to 13F XML issuer_name
    df["company_name"] = df.apply(
        lambda r: cusip_map.get(r["cusip"], {}).get("name") or r["issuer_name"],
        axis=1,
    )
    # Preserve raw 13F titleOfClass as security_class and map ticker SIC codes to broad sectors
    df["security_class"] = df["title_of_class"]
    unique_tickers = [t for t in df["ticker"].dropna().unique().tolist() if t]
    sector_map = map_sectors(unique_tickers)
    df["sector"] = df["ticker"].map(
        lambda t: sector_map.get(str(t).upper(), "Unknown") if pd.notna(t) and t else "Unknown"
    )

    os.makedirs(os.path.join("data", "processed"), exist_ok=True)
    processed_path = os.path.join("data", "processed", "holdings_mapped.csv")
    df.to_csv(processed_path, index=False)
    logger.info("Saved mapped holdings to %s", processed_path)

    logger.info("Step 3/4: Creating database schema and loading star schema tables...")
    create_schema()
    bulk_insert_holdings(df)

    with get_connection() as conn:
        for table in ("Dim_Fund", "Dim_Security", "Fact_Holdings"):
            count = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()["cnt"]
            logger.info("Table %s row count: %d", table, count)

    logger.info("Step 4/4: Exporting Power BI CSVs to output/...")
    export_to_csv(get_convergence_signals("2026-Q2", min_funds=4), "convergence_signals.csv")
    export_to_csv(
        get_convergence_signals("2026-Q2", fund_types=DISCRETIONARY_FUND_TYPES),
        "discretionary_signals.csv",
    )
    export_to_csv(get_top_holdings_by_aum("2026-Q2", top_n=50), "top_holdings.csv")
    export_to_csv(get_fund_summary(), "fund_summary.csv")
    export_to_csv(get_sector_by_period(), "sector_by_period.csv")

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_pipeline()

    print("\n=== Table Row Counts ===")
    with get_connection() as conn:
        for tbl in ("Dim_Fund", "Dim_Security", "Fact_Holdings"):
            cnt = conn.execute(f"SELECT COUNT(*) AS cnt FROM {tbl}").fetchone()["cnt"]
            print(f"{tbl}: {cnt:,}")

        cov = conn.execute(
            """
            SELECT
                ROUND(SUM(CASE WHEN s.sector != 'Unknown' THEN h.value_usd ELSE 0 END) * 100.0 / SUM(h.value_usd), 2) AS all_cov_pct,
                ROUND(
                    SUM(CASE WHEN s.sector != 'Unknown' AND (h.put_call IS NULL OR h.put_call = '') THEN h.value_usd ELSE 0 END) * 100.0
                    / SUM(CASE WHEN h.put_call IS NULL OR h.put_call = '' THEN h.value_usd ELSE 0 END),
                    2
                ) AS eq_cov_pct
            FROM Fact_Holdings h
            JOIN Dim_Security s ON h.security_id = s.security_id
            WHERE h.value_usd > 0
            """
        ).fetchone()
        print(
            f"\n=== Sector Coverage ===\n"
            f"All holdings (including options): {cov['all_cov_pct']:.2f}%\n"
            f"Common equity (excluding options): {cov['eq_cov_pct']:.2f}%"
        )

    print("\n=== Total AUM per Period (With and Without Options) ===")
    print(get_aum_by_period().to_string(index=False))

    print("\n=== Top 10 Holdings for Berkshire Hathaway (2026-Q2) ===")
    print(get_fund_concentration("Berkshire Hathaway", "2026-Q2").to_string(index=False))

    print("\n=== Full Universe Convergence Signals (2026-Q2, Top 15) ===")
    full_signals = get_convergence_signals("2026-Q2", min_funds=4)
    print(f"Total full-universe convergence signals (4+ funds): {len(full_signals)}")
    print(full_signals.head(15).to_string(index=False))

    print("\n=== Discretionary Convergence Signals (2026-Q2, Conglomerate/Pension/SWF) ===")
    disc_signals = get_convergence_signals("2026-Q2", fund_types=DISCRETIONARY_FUND_TYPES)
    print(f"Total discretionary convergence signals (2+ of 3 discretionary funds): {len(disc_signals)}")
    print(disc_signals.head(15).to_string(index=False))


