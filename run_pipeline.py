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
    get_etf_convergence_signals,
    get_fund_aum,
    get_fund_concentration,
    get_fund_summary,
    get_new_to_sample_signals,
    get_sector_by_period,
    get_top_holdings_by_aum,
)
from src.cusip_mapper import map_cusips, map_sectors
from src.database import bulk_insert_holdings, create_schema, detect_splits, get_connection
from src.parse_holdings import parse_all_raw_files, validate_parsed_data

logger = logging.getLogger(__name__)

DISCRETIONARY_FUND_TYPES = [
    "Conglomerate",
    "Public Pension Fund",
    "Sovereign Wealth Fund",
]


def run_pipeline(
    data_dir: str = "data",
    db_path: str | None = None,
    output_dir: str = "output",
    user_agent: str | None = None,
) -> pd.DataFrame:
    """
    Executes the full 13F data pipeline:
    1. Parse and aggregate raw 13F XML files from <data_dir>/raw/
    2. Map unique CUSIPs to tickers/names via OpenFIGI + cache, and map tickers to SIC sectors
    3. Detect stock splits (confirming via yfinance + split_cache.json), load funds, securities, and split-adjusted holdings into SQLite
    4. Export Power BI CSVs to <output_dir>/
    
    Args:
        data_dir (str): Root data directory containing raw/, mappings/, and processed/. Defaults to 'data'.
        db_path (str | None): Optional SQLite database file path. Defaults to <data_dir>/sec_13f.db (or config.DB_PATH when data_dir=='data').
        output_dir (str): Output directory for exported CSVs. Defaults to 'output'.
        user_agent (str | None): Optional SEC User-Agent header override.
        
    Returns:
        pd.DataFrame: The parsed and mapped DataFrame loaded into the database.
    """
    import config

    resolved_db_path = db_path or (config.DB_PATH if data_dir == "data" else os.path.join(data_dir, "sec_13f.db"))
    raw_dir = os.path.join(data_dir, "raw")
    mappings_dir = os.path.join(data_dir, "mappings")
    cusip_cache_path = os.path.join(mappings_dir, "cusip_cache.json")
    sector_cache_path = os.path.join(mappings_dir, "sector_cache.json")
    split_cache_path = os.path.join(mappings_dir, "split_cache.json")

    logger.info("Step 1/4: Parsing and aggregating raw 13F XML files from %s...", raw_dir)
    df = parse_all_raw_files(raw_dir=raw_dir)
    df = validate_parsed_data(df)

    logger.info("Step 2/4: Mapping %d unique CUSIPs and resolving SIC sectors...", df["cusip"].nunique())
    unique_cusips = df["cusip"].unique().tolist()
    cusip_map = map_cusips(unique_cusips, cache_path=cusip_cache_path)

    df["ticker"] = df["cusip"].map(lambda c: cusip_map.get(c, {}).get("ticker"))
    # Prefer OpenFIGI canonical company name when available, falling back to 13F XML issuer_name
    df["company_name"] = df.apply(
        lambda r: cusip_map.get(r["cusip"], {}).get("name") or r["issuer_name"],
        axis=1,
    )
    # Preserve raw 13F titleOfClass as security_class and map ticker SIC codes to broad sectors
    df["security_class"] = df["title_of_class"]
    unique_tickers = [t for t in df["ticker"].dropna().unique().tolist() if t]
    sector_map = map_sectors(unique_tickers, cache_path=sector_cache_path, user_agent=user_agent)
    df["sector"] = df["ticker"].map(
        lambda t: sector_map.get(str(t).upper(), "Unknown") if pd.notna(t) and t else "Unknown"
    )

    processed_dir = os.path.join(data_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    processed_path = os.path.join(processed_dir, "holdings_mapped.csv")
    df.to_csv(processed_path, index=False)
    logger.info("Saved mapped holdings to %s", processed_path)

    logger.info("Step 3/4: Creating database schema and loading star schema tables into %s...", resolved_db_path)
    create_schema(db_path=resolved_db_path)
    bulk_insert_holdings(df, db_path=resolved_db_path, split_cache_path=split_cache_path)

    with get_connection(db_path=resolved_db_path) as conn:
        for table in ("Dim_Fund", "Dim_Security", "Fact_Holdings"):
            count = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table}").fetchone()["cnt"]
            logger.info("Table %s row count: %d", table, count)

    logger.info("Step 4/4: Exporting Power BI CSVs to %s...", output_dir)
    export_to_csv(
        get_convergence_signals("2026-Q2", min_funds=4, db_path=resolved_db_path),
        "convergence_signals.csv",
        output_dir=output_dir,
    )
    export_to_csv(
        get_convergence_signals("2026-Q2", fund_types=DISCRETIONARY_FUND_TYPES, db_path=resolved_db_path),
        "discretionary_signals.csv",
        output_dir=output_dir,
    )
    export_to_csv(
        get_new_to_sample_signals("2026-Q2", min_funds=3, db_path=resolved_db_path),
        "new_positions_signals.csv",
        output_dir=output_dir,
    )
    export_to_csv(
        get_top_holdings_by_aum("2026-Q2", top_n=50, db_path=resolved_db_path),
        "top_holdings.csv",
        output_dir=output_dir,
    )
    export_to_csv(get_fund_aum(db_path=resolved_db_path), "fund_aum.csv", output_dir=output_dir)
    export_to_csv(get_fund_summary(db_path=resolved_db_path), "fund_summary.csv", output_dir=output_dir)
    export_to_csv(get_sector_by_period(db_path=resolved_db_path), "sector_by_period.csv", output_dir=output_dir)

    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df_pipeline = run_pipeline()

    print("\n=== Detected Stock Splits (Confirmed vs Unconfirmed via yfinance) ===")
    splits_df = detect_splits(df_pipeline)
    print(splits_df.to_string(index=False))

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

    print("\n=== Full Universe Convergence Signals (2026-Q2, Top 15, Issuer-Merged, Excl. New to Sample & ETFs) ===")
    full_signals = get_convergence_signals("2026-Q2", min_funds=4)
    print(f"Total full-universe convergence signals (4+ funds): {len(full_signals)}")
    print(full_signals.head(15).to_string(index=False))

    print("\n=== Discretionary Convergence Signals (2026-Q2, 3 Discretionary Funds, Issuer-Merged) ===")
    disc_signals = get_convergence_signals("2026-Q2", fund_types=DISCRETIONARY_FUND_TYPES)
    print(f"Total discretionary convergence signals (2+ of 3 discretionary funds): {len(disc_signals)}")
    print(disc_signals.head(15).to_string(index=False))

    print("\n=== New to the sample (no prior-quarter holders) (2026-Q2, Separate Table, is_new_listing = 1) ===")
    new_to_sample = get_new_to_sample_signals("2026-Q2", min_funds=3)
    print(f"Total New to the sample (no prior-quarter holders) signals (3+ funds): {len(new_to_sample)}")
    print(new_to_sample.to_string(index=False))

    print("\n=== ETF & Index Trust Convergence Signals (2026-Q2, Separate Table) ===")
    etf_signals = get_etf_convergence_signals("2026-Q2", min_funds=3)
    print(f"Total ETF/Index Trust convergence signals (3+ funds): {len(etf_signals)}")
    print(etf_signals.to_string(index=False))




