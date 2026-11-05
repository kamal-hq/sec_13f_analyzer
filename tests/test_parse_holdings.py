"""
Pytest suite for src/parse_holdings.py and database/cover-page reconciliation using the real 13F XML files in data/raw/.
"""

import os
import pandas as pd
import pytest
from config import COVER_PAGE_TOTALS, FILING_PERIODS
from src.database import get_connection
from src.parse_holdings import (
    aggregate_holdings,
    extract_fund_metadata,
    parse_all_raw_files,
    parse_xml_file,
    validate_parsed_data,
)

RAW_DIR = os.path.join("data", "raw")
BERKSHIRE_Q1 = os.path.join(RAW_DIR, "0001067983_0001193125-26-226661.xml")
BERKSHIRE_Q2 = os.path.join(RAW_DIR, "0001067983_0001193125-26-352200.xml")
CITADEL_Q1 = os.path.join(RAW_DIR, "0001423053_0001104659-26-062477.xml")
CITADEL_Q2_RESTATED = os.path.join(RAW_DIR, "0001423053_0001104659-26-104387.xml")


@pytest.fixture(scope="module")
def all_parsed_df() -> pd.DataFrame:
    """Parses and aggregates all 14 real XML files once per test module."""
    return parse_all_raw_files(RAW_DIR)


@pytest.mark.parametrize(
    "file_path,expected_cik,expected_period,expected_name",
    [
        (BERKSHIRE_Q1, "0001067983", "2026-Q1", "Berkshire Hathaway"),
        (BERKSHIRE_Q2, "0001067983", "2026-Q2", "Berkshire Hathaway"),
        (CITADEL_Q1, "0001423053", "2026-Q1", "Citadel Advisors"),
        (CITADEL_Q2_RESTATED, "0001423053", "2026-Q2", "Citadel Advisors"),
    ],
)
def test_extract_fund_metadata(
    file_path: str,
    expected_cik: str,
    expected_period: str,
    expected_name: str,
) -> None:
    """Verifies CIK and reporting period extraction from filename and FILING_PERIODS."""
    meta = extract_fund_metadata(file_path)
    assert meta["cik"] == expected_cik
    assert meta["fund_cik"] == expected_cik
    assert meta["period"] == expected_period
    assert meta["fund_name"] == expected_name


@pytest.mark.parametrize(
    "file_path,expected_raw_rows",
    [
        (BERKSHIRE_Q1, 90),
        (BERKSHIRE_Q2, 89),
        (CITADEL_Q1, 15589),
        (CITADEL_Q2_RESTATED, 16122),
    ],
)
def test_parse_xml_file_row_counts_and_invariants(file_path: str, expected_raw_rows: int) -> None:
    """Checks raw row counts, 9-character CUSIPs, and non-negative values/shares per XML file."""
    rows = parse_xml_file(file_path)
    assert len(rows) == expected_raw_rows

    for row in rows:
        assert isinstance(row["cusip"], str)
        assert len(row["cusip"]) == 9, f"Invalid CUSIP length: {row['cusip']}"
        assert row["value"] >= 0, f"Negative value for {row['cusip']}"
        assert row["shares"] >= 0, f"Negative shares for {row['cusip']}"
        assert row["voting_authority_sole"] >= 0


def test_values_are_in_exact_usd_not_multiplied_by_1000() -> None:
    """Verifies post-2023 13F <value> is kept in exact USD and not multiplied by 1000."""
    rows = parse_xml_file(BERKSHIRE_Q1)
    first = rows[0]
    assert first["cusip"] == "02005N100"
    assert first["issuer_name"] == "ALLY FINL INC"
    assert first["value"] == 498_992_850
    assert first["shares"] == 12_719_675


def test_aggregated_row_counts_and_no_duplicates(all_parsed_df: pd.DataFrame) -> None:
    """Verifies multi-manager rows are aggregated per (fund_cik, period, cusip, put_call) across all 7 funds."""
    assert len(all_parsed_df) == 46_865
    assert all_parsed_df["fund_cik"].nunique() == 7
    assert set(all_parsed_df["period"].unique()) == {"2026-Q1", "2026-Q2"}

    counts = all_parsed_df.groupby(["fund_cik", "period"]).size().to_dict()
    assert counts[("0001067983", "2026-Q1")] == 29
    assert counts[("0001067983", "2026-Q2")] == 29
    assert counts[("0001423053", "2026-Q1")] == 12_857
    assert counts[("0001423053", "2026-Q2")] == 13_572

    # No duplicate (fund_cik, period, cusip, put_call) combinations should remain
    dups = all_parsed_df.duplicated(subset=["fund_cik", "period", "cusip", "put_call"], keep=False)
    assert int(dups.sum()) == 0


def test_aggregated_cusips_and_non_negative_values(all_parsed_df: pd.DataFrame) -> None:
    """Verifies all CUSIPs are 9 characters and no negative values or shares exist."""
    assert (all_parsed_df["cusip"].str.len() == 9).all()
    assert (all_parsed_df["value"] >= 0).all()
    assert (all_parsed_df["shares"] > 0).all()
    assert not all_parsed_df[["cusip", "issuer_name", "value", "shares"]].isna().any().any()

    # Check Apple aggregation for Berkshire Q2 2026
    aapl_q2 = all_parsed_df[
        (all_parsed_df["fund_cik"] == "0001067983")
        & (all_parsed_df["period"] == "2026-Q2")
        & (all_parsed_df["cusip"] == "037833100")
    ]
    assert len(aapl_q2) == 1
    assert int(aapl_q2.iloc[0]["value"]) == 65_950_296_923
    assert int(aapl_q2.iloc[0]["shares"]) == 227_917_808


def test_put_call_column_preserved_for_citadel(all_parsed_df: pd.DataFrame) -> None:
    """Verifies put_call is preserved for Citadel option rows and None for Berkshire equity."""
    assert "put_call" in all_parsed_df.columns
    berk = all_parsed_df[all_parsed_df["fund_cik"] == "0001067983"]
    assert berk["put_call"].isna().all()

    citadel = all_parsed_df[all_parsed_df["fund_cik"] == "0001423053"]
    put_call_vals = set(citadel["put_call"].dropna().unique())
    assert put_call_vals == {"Put", "Call"}


def test_validate_parsed_data_handles_unaggregated_input() -> None:
    """Verifies validate_parsed_data aggregates duplicate rows when passed raw unaggregated rows."""
    raw_rows = parse_xml_file(BERKSHIRE_Q1)
    raw_df = pd.DataFrame(raw_rows)
    raw_df["fund_cik"] = "0001067983"
    raw_df["period"] = "2026-Q1"
    cleaned_df = validate_parsed_data(raw_df)
    assert len(raw_df) == 90
    assert len(cleaned_df) == 29
    assert len(aggregate_holdings(cleaned_df)) == 29


@pytest.mark.parametrize("accession,expected_table_value_total", list(COVER_PAGE_TOTALS.items()))
def test_fund_period_sum_value_matches_cover_page_table_value_total(
    all_parsed_df: pd.DataFrame,
    accession: str,
    expected_table_value_total: int,
) -> None:
    """
    Compares each fund-period's SUM(value_usd) (both in parsed DataFrame and in SQLite Fact_Holdings)
    against the <tableValueTotal> reported on the filing's cover page (primary_doc.xml).
    """
    filing_df = all_parsed_df[all_parsed_df["accession_number"] == accession]
    assert not filing_df.empty, f"No parsed rows found for accession {accession}"

    parsed_sum = int(filing_df["value"].sum())
    assert parsed_sum == expected_table_value_total, (
        f"Parsed sum {parsed_sum:,} != cover page tableValueTotal {expected_table_value_total:,} for {accession}"
    )

    fund_cik = filing_df["fund_cik"].iloc[0]
    period = FILING_PERIODS[accession]
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                SUM(h.value_usd) AS db_sum,
                SUM(CASE WHEN h.qoq_change_flag IS NOT NULL THEN 1 ELSE 0 END) AS non_null_flags
            FROM Fact_Holdings h
            JOIN Dim_Fund f ON h.fund_id = f.fund_id
            WHERE f.cik = ? AND h.period = ?
            """,
            (fund_cik, period),
        ).fetchone()
        assert int(row["db_sum"]) == expected_table_value_total
        # Earliest period (2026-Q1) must have NULL qoq_change_flag for all rows
        if period == "2026-Q1":
            assert int(row["non_null_flags"]) == 0


def test_dim_security_has_security_class_and_sector_coverage() -> None:
    """Verifies Dim_Security stores security_class and maps SIC sectors covering >70% of equity value."""
    with get_connection() as conn:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(Dim_Security)").fetchall()]
        assert "security_class" in cols
        assert "sector" in cols

        cov = conn.execute(
            """
            SELECT
                SUM(CASE WHEN s.sector != 'Unknown' AND (h.put_call IS NULL OR h.put_call = '') THEN h.value_usd ELSE 0 END) * 100.0
                / SUM(CASE WHEN h.put_call IS NULL OR h.put_call = '' THEN h.value_usd ELSE 0 END) AS eq_cov_pct
            FROM Fact_Holdings h
            JOIN Dim_Security s ON h.security_id = s.security_id
            WHERE h.value_usd > 0
            """
        ).fetchone()
        assert float(cov["eq_cov_pct"]) >= 75.0


def test_redefined_convergence_signals_and_discretionary_subset() -> None:
    """Verifies get_convergence_signals enforces >=4 funds, >=10% share increase or NEW, >=$1M added, and fund_types."""
    from src.analysis import get_convergence_signals

    full_df = get_convergence_signals("2026-Q2", min_funds=4)
    assert not full_df.empty
    expected_cols = {
        "cusip",
        "ticker",
        "company_name",
        "sector",
        "funds_buying",
        "funds",
        "total_dollars_added",
        "fund_type_breakdown",
    }
    assert expected_cols.issubset(set(full_df.columns))
    assert (full_df["funds_buying"] >= 4).all()
    assert (full_df["total_dollars_added"] >= 4_000_000).all()

    disc_df = get_convergence_signals(
        "2026-Q2",
        fund_types=["Conglomerate", "Public Pension Fund", "Sovereign Wealth Fund"],
    )
    assert not disc_df.empty
    assert (disc_df["funds_buying"] >= 2).all()
    assert "GOOGL" in disc_df["ticker"].values


def test_all_six_sql_queries_execute_cleanly() -> None:
    """Executes all 6 queries in sql/queries.sql against data/sec_13f.db and verifies non-empty results."""
    with open(os.path.join("sql", "queries.sql"), "r", encoding="utf-8") as f:
        sql_text = f.read()

    statements = [stmt.strip() for stmt in sql_text.split(";") if stmt.strip()]
    assert len(statements) == 6, f"Expected 6 SQL queries in sql/queries.sql, found {len(statements)}"

    with get_connection() as conn:
        for i, stmt in enumerate(statements, 1):
            df_q = pd.read_sql_query(stmt, conn)
            assert not df_q.empty, f"Query #{i} in sql/queries.sql returned 0 rows"

