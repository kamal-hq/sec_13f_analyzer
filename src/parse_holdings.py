"""
Parses 13F-HR XML files from data/raw/ and extracts individual holding records.
"""

import logging
import os
from typing import Any
import xml.etree.ElementTree as ET
import pandas as pd
import config
from config import FILING_PERIODS, TARGET_FUNDS

logger = logging.getLogger(__name__)

# Root namespace for SEC 13F information table XML documents
NS: dict[str, str] = {"ns": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}

# Reverse lookup from padded CIK to human-readable fund name
CIK_TO_FUND_NAME: dict[str, str] = {cik: name for name, cik in TARGET_FUNDS.items()}


def _find_text(element: ET.Element, path: str, default: str = "") -> str:
    """Extracts stripped text from a namespaced child element, returning default if absent."""
    node = element.find(path, NS)
    if node is not None and node.text is not None:
        return node.text.strip()
    return default


def parse_xml_file(file_path: str) -> list[dict[str, Any]]:
    """
    Parses a single 13F-HR information table XML file using ElementTree.
    
    Uses the 13F informationTable namespace (NS) for every find/findall lookup.
    Extracts the following fields per <infoTable>: cusip, issuer_name, title_of_class,
    value (in USD), shares, share_type, put_call, investment_discretion, voting_authority_sole.
    
    Note: Post-2023 SEC 13F <value> is already reported in exact US dollars and must NOT be multiplied by 1000.
    
    Args:
        file_path (str): Path to the XML file.
        
    Returns:
        list[dict]: A list of holding records extracted from the XML.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    holdings: list[dict[str, Any]] = []
    for info in root.findall("ns:infoTable", NS):
        issuer_name = _find_text(info, "ns:nameOfIssuer")
        title_of_class = _find_text(info, "ns:titleOfClass")
        cusip = _find_text(info, "ns:cusip").upper()
        # Post-2023 13F values are already in exact USD; do not multiply by 1000
        value_str = _find_text(info, "ns:value", "0")
        shares_str = _find_text(info, "ns:shrsOrPrnAmt/ns:sshPrnamt", "0")
        share_type = _find_text(info, "ns:shrsOrPrnAmt/ns:sshPrnamtType")
        investment_discretion = _find_text(info, "ns:investmentDiscretion")
        put_call_raw = _find_text(info, "ns:putCall")
        put_call: str | None = put_call_raw if put_call_raw else None
        sole_str = _find_text(info, "ns:votingAuthority/ns:Sole", "0")

        holdings.append(
            {
                "cusip": cusip,
                "issuer_name": issuer_name,
                "title_of_class": title_of_class,
                "value": int(float(value_str)),
                "shares": int(float(shares_str)),
                "share_type": share_type,
                "put_call": put_call,
                "investment_discretion": investment_discretion,
                "voting_authority_sole": int(float(sole_str)),
            }
        )

    logger.info("Parsed %d raw rows from %s", len(holdings), file_path)
    return holdings


def extract_fund_metadata(
    file_path: str,
    filing_periods: dict[str, str] | None = None,
    target_funds: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Extracts the fund CIK, accession number, fund name, and report period from the filename
    ({cik}_{accession}.xml) and the FILING_PERIODS mapping in config.py, because raw files
    are information-table-only XMLs with no cover page.
    
    Args:
        file_path (str): Path to the XML file.
        filing_periods (dict[str, str] | None): Optional accession -> period mapping override.
        target_funds (dict[str, str] | None): Optional fund_name -> cik mapping override.
        
    Returns:
        dict: A dictionary containing fund metadata (cik, fund_cik, fund_name, accession_number, period).
    """
    basename = os.path.basename(file_path)
    stem, _ = os.path.splitext(basename)
    if "_" not in stem:
        raise ValueError(f"Expected filename format {{cik}}_{{accession}}.xml, got: {basename}")

    cik, accession = stem.split("_", 1)
    cik = cik.zfill(10)
    periods_map = filing_periods if filing_periods is not None else FILING_PERIODS
    period = periods_map.get(accession)
    if period is None:
        logger.warning("Accession %s not found in FILING_PERIODS; defaulting to UNKNOWN", accession)
        period = "UNKNOWN"

    if target_funds is not None:
        cik_map = {v.zfill(10): k for k, v in target_funds.items()}
    else:
        cik_map = CIK_TO_FUND_NAME
    fund_name = cik_map.get(cik, f"CIK {cik}")
    return {
        "cik": cik,
        "fund_cik": cik,
        "fund_name": fund_name,
        "accession_number": accession,
        "period": period,
    }


def aggregate_holdings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates holding rows split across multiple otherManager entries within the same filing.
    Groups per (fund, period, cusip, put_call) and sums value, shares, and voting_authority_sole.
    
    Args:
        df (pd.DataFrame): DataFrame of parsed holdings.
        
    Returns:
        pd.DataFrame: Aggregated DataFrame with one row per (fund, period, cusip, put_call).
    """
    if df.empty:
        return df.copy()

    # Determine grouping columns based on metadata present in the DataFrame
    group_cols = [c for c in ["fund_cik", "period", "cusip", "put_call"] if c in df.columns]
    if not group_cols:
        group_cols = ["cusip", "put_call"]

    agg_spec: dict[str, str] = {}
    for col in df.columns:
        if col in group_cols:
            continue
        if col in ("value", "value_usd", "shares", "voting_authority_sole"):
            agg_spec[col] = "sum"
        else:
            agg_spec[col] = "first"

    # Use dropna=False so common equity rows (where put_call is None) are preserved in grouping
    aggregated = df.groupby(group_cols, dropna=False, as_index=False).agg(agg_spec)

    # Restore standard column order
    ordered_cols = [c for c in df.columns if c in aggregated.columns]
    return aggregated[ordered_cols]


def validate_parsed_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Checks for missing CUSIPs, null/negative values, and duplicate holdings in the DataFrame.
    Logs a warning for each issue found and aggregates duplicate (fund, cusip, put_call) rows.
    
    Args:
        df (pd.DataFrame): The raw parsed DataFrame.
        
    Returns:
        pd.DataFrame: The cleaned and aggregated DataFrame.
    """
    if df.empty:
        logger.warning("Parsed DataFrame is empty.")
        return df.copy()

    cleaned = df.copy()

    # 1. Check for missing or malformed CUSIPs (must be 9 characters)
    missing_cusip = cleaned["cusip"].isna() | (cleaned["cusip"].astype(str).str.strip() == "")
    if missing_cusip.any():
        logger.warning("Dropping %d rows with missing CUSIP.", int(missing_cusip.sum()))
        cleaned = cleaned[~missing_cusip]

    bad_len_cusip = cleaned["cusip"].astype(str).str.len() != 9
    if bad_len_cusip.any():
        logger.warning("Found %d rows where CUSIP is not 9 characters.", int(bad_len_cusip.sum()))

    # 2. Check for null values in required fields
    required_cols = [c for c in ["cusip", "issuer_name", "value", "shares"] if c in cleaned.columns]
    null_mask = cleaned[required_cols].isna().any(axis=1)
    if null_mask.any():
        logger.warning("Dropping %d rows with null values in required columns.", int(null_mask.sum()))
        cleaned = cleaned[~null_mask]

    # 3. Check for negative values or shares
    neg_mask = (cleaned["value"] < 0) | (cleaned["shares"] < 0)
    if neg_mask.any():
        logger.warning("Dropping %d rows with negative value or shares.", int(neg_mask.sum()))
        cleaned = cleaned[~neg_mask]

    # 4. Check for duplicate holdings split by otherManager and aggregate if present
    dedup_cols = [c for c in ["fund_cik", "period", "cusip", "put_call"] if c in cleaned.columns]
    dup_count = int(cleaned.duplicated(subset=dedup_cols, keep=False).sum())
    if dup_count > 0:
        logger.warning(
            "Found %d rows with duplicate %s (otherManager splits); aggregating by summing value and shares.",
            dup_count,
            dedup_cols,
        )
        cleaned = aggregate_holdings(cleaned)

    return cleaned.reset_index(drop=True)


def parse_all_raw_files(
    raw_dir: str | None = None,
    filing_periods: dict[str, str] | None = None,
    target_funds: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Iterates all .xml files in raw_dir (defaults to <DATA_DIR>/raw), calls parse_xml_file and extract_fund_metadata for each,
    combines the extracted data into a single DataFrame with a fund_cik column added,
    and aggregates per (fund, period, cusip, put_call) by summing value and shares.
    
    Returns:
        pd.DataFrame: A DataFrame containing all validated and aggregated holdings and fund metadata.
    """
    resolved_raw_dir = raw_dir or os.path.join(config.DATA_DIR, "raw")
    if not os.path.exists(resolved_raw_dir):
        logger.warning("Raw directory %s does not exist.", resolved_raw_dir)
        return pd.DataFrame()

    xml_files = sorted(
        os.path.join(resolved_raw_dir, f) for f in os.listdir(resolved_raw_dir) if f.lower().endswith(".xml")
    )
    all_dfs: list[pd.DataFrame] = []

    for file_path in xml_files:
        meta = extract_fund_metadata(
            file_path,
            filing_periods=filing_periods,
            target_funds=target_funds,
        )
        records = parse_xml_file(file_path)
        if not records:
            continue
        file_df = pd.DataFrame(records)
        file_df["fund_cik"] = meta["fund_cik"]
        file_df["fund_name"] = meta["fund_name"]
        file_df["period"] = meta["period"]
        file_df["accession_number"] = meta["accession_number"]
        all_dfs.append(file_df)

    if not all_dfs:
        return pd.DataFrame()

    combined_df = pd.concat(all_dfs, ignore_index=True)
    # Validate and aggregate multi-manager rows per (fund_cik, period, cusip, put_call)
    validated_df = validate_parsed_data(combined_df)
    aggregated_df = aggregate_holdings(validated_df)
    logger.info(
        "Parsed %d total raw rows across %d files -> %d aggregated holdings.",
        len(combined_df),
        len(xml_files),
        len(aggregated_df),
    )
    return aggregated_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df_parsed = parse_all_raw_files()
    print(f"Total aggregated holdings: {len(df_parsed)}")
    print(df_parsed.head())

