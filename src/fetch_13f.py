"""
Fetches 13F-HR and 13F-HR/A filing metadata and information table XML files from SEC EDGAR
for each fund in TARGET_FUNDS.
"""

import json
import logging
import os
import re
import time
from typing import Any
import xml.etree.ElementTree as ET
import requests
import config
from config import (
    COVER_PAGE_TOTALS,
    EDGAR_BASE_URL,
    FILING_PERIODS,
    RATE_LIMIT_DELAY,
    SEC_BASE_URL,
    SEC_USER_AGENT,
    TARGET_FUNDS,
)

logger = logging.getLogger(__name__)

_SESSION = requests.Session()
COVER_NS = {"n": "http://www.sec.gov/edgar/thirteenffiler"}
METADATA_CACHE_PATH = os.path.join("data", "mappings", "filing_metadata.json")


def make_request(url: str, user_agent: str | None = None) -> dict[str, Any]:
    """
    Handles a single SEC API request with proper User-Agent header, rate limiting delay, and error handling.
    This is the only function that should make HTTP calls.
    
    Args:
        url (str): The URL to request.
        user_agent (str | None): Optional SEC User-Agent header override.
        
    Returns:
        dict: The JSON response parsed into a dictionary (or {"text": ...} for XML/text responses).
    """
    # SEC requires a descriptive User-Agent header and enforces <=10 requests/second
    resolved_ua = user_agent or os.getenv("SEC_USER_AGENT", config.SEC_USER_AGENT)
    headers = {"User-Agent": resolved_ua, "Accept-Encoding": "gzip, deflate"}
    time.sleep(RATE_LIMIT_DELAY)
    try:
        response = _SESSION.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type or url.endswith(".json"):
            return response.json()
        return {"text": response.text}
    except requests.RequestException as exc:
        logger.error("SEC request failed for %s: %s", url, exc)
        raise


def _inspect_filing_cover_page(
    cik: str,
    accession_number: str,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """
    Reads the filing's index.json and primary_doc.xml cover page to find the information table
    XML filename, amendmentType (RESTATEMENT vs NEW HOLDINGS), tableEntryTotal, and tableValueTotal.
    """
    cik_int = str(int(cik))
    acc_no_hyphens = accession_number.replace("-", "")
    index_url = f"{EDGAR_BASE_URL}/data/{cik_int}/{acc_no_hyphens}/index.json"
    index_data = make_request(index_url, user_agent=user_agent)

    items = index_data.get("directory", {}).get("item", [])
    xml_files = [item.get("name", "") for item in items if item.get("name", "").endswith(".xml")]
    primary_doc = next((f for f in xml_files if "primary_doc" in f.lower()), None)
    infotable_doc = next((f for f in xml_files if "primary_doc" not in f.lower()), None)

    info: dict[str, Any] = {
        "primary_doc": primary_doc,
        "infotable_doc": infotable_doc,
        "is_amendment": False,
        "amendment_type": None,
        "table_entry_total": None,
        "table_value_total": None,
    }

    if primary_doc:
        cover_url = f"{EDGAR_BASE_URL}/data/{cik_int}/{acc_no_hyphens}/{primary_doc}"
        cover_resp = make_request(cover_url, user_agent=user_agent)
        try:
            root = ET.fromstring(cover_resp["text"])
            is_amd = root.findtext(".//n:isAmendment", default="false", namespaces=COVER_NS).strip().lower() == "true"
            amd_type = root.findtext(".//n:amendmentType", default="", namespaces=COVER_NS).strip().upper() or None
            entry_tot = root.findtext(".//n:tableEntryTotal", default="", namespaces=COVER_NS).strip()
            val_tot = root.findtext(".//n:tableValueTotal", default="", namespaces=COVER_NS).strip()
            info["is_amendment"] = is_amd
            info["amendment_type"] = amd_type
            info["table_entry_total"] = int(entry_tot) if entry_tot.isdigit() else None
            info["table_value_total"] = int(val_tot) if val_tot.isdigit() else None
        except ET.ParseError as exc:
            logger.warning("Could not parse primary_doc.xml for %s / %s: %s", cik, accession_number, exc)

    return info


def _update_filing_periods_config(
    accession: str,
    period: str,
    table_value_total: int | None = None,
    superseded_accessions: list[str] | None = None,
    metadata_cache_path: str | None = None,
) -> None:
    """Updates FILING_PERIODS and COVER_PAGE_TOTALS in memory, on disk, and in config.py."""
    for old_acc in superseded_accessions or []:
        FILING_PERIODS.pop(old_acc, None)
        COVER_PAGE_TOTALS.pop(old_acc, None)

    FILING_PERIODS[accession] = period
    if table_value_total is not None:
        COVER_PAGE_TOTALS[accession] = table_value_total

    # Persist metadata JSON
    resolved_cache_path = metadata_cache_path or os.path.join(config.DATA_DIR, "mappings", "filing_metadata.json")
    os.makedirs(os.path.dirname(resolved_cache_path), exist_ok=True)
    meta_store = {
        "filing_periods": dict(FILING_PERIODS),
        "cover_page_totals": dict(COVER_PAGE_TOTALS),
    }
    with open(resolved_cache_path, "w", encoding="utf-8") as f:
        json.dump(meta_store, f, indent=2, sort_keys=True)

    # Also update FILING_PERIODS and COVER_PAGE_TOTALS literals in config.py
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.py")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
        fp_lines = ["FILING_PERIODS: dict[str, str] = {"]
        for k, v in FILING_PERIODS.items():
            fp_lines.append(f'    "{k}": "{v}",')
        fp_lines.append("}")
        content = re.sub(
            r"FILING_PERIODS:\s*dict\[str,\s*str\]\s*=\s*\{[^}]*\}",
            "\n".join(fp_lines),
            content,
        )
        ct_lines = ["COVER_PAGE_TOTALS: dict[str, int] = {"]
        for k, v in COVER_PAGE_TOTALS.items():
            ct_lines.append(f'    "{k}": {v},')
        ct_lines.append("}")
        content = re.sub(
            r"COVER_PAGE_TOTALS:\s*dict\[str,\s*int\]\s*=\s*\{[^}]*\}",
            "\n".join(ct_lines),
            content,
        )
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(content)


def get_fund_filings(
    cik: str,
    year: int,
    quarter: int,
    raw_dir: str | None = None,
    user_agent: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetches the list of 13F-HR (and 13F-HR/A amendment) filings for a CIK in a given quarter
    from the SEC submissions endpoint.
    
    If a 13F-HR/A amendment is a full RESTATEMENT, uses the latest restatement and ignores
    the superseded original 13F-HR filing. If partial (NEW HOLDINGS), keeps both for merging.
    
    Args:
        cik (str): Central Index Key of the fund.
        year (int): The reporting year.
        quarter (int): The reporting quarter (1-4).
        raw_dir (str | None): Optional directory for raw XML files (defaults to <DATA_DIR>/raw).
        user_agent (str | None): Optional SEC User-Agent header override.
        
    Returns:
        list[dict]: List of dictionaries with keys: accession_number, filed_date, period_of_report,
                    form, amendment_type, table_entry_total, table_value_total, infotable_doc.
    """
    resolved_raw_dir = raw_dir or os.path.join(config.DATA_DIR, "raw")
    padded_cik = cik.zfill(10)
    url = f"{SEC_BASE_URL}/submissions/CIK{padded_cik}.json"
    data = make_request(url, user_agent=user_agent)

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])

    # Map quarter number to the calendar month of the 13F report period end
    quarter_end_months = {1: "03", 2: "06", 3: "09", 4: "12"}
    target_month = quarter_end_months.get(quarter, "")
    target_prefix = f"{year}-{target_month}"

    candidates: list[dict[str, Any]] = []
    for form, acc, f_date, r_date in zip(forms, accessions, filing_dates, report_dates):
        if form in ("13F-HR", "13F-HR/A") and str(r_date).startswith(target_prefix):
            cover_info = _inspect_filing_cover_page(padded_cik, acc, user_agent=user_agent)
            candidates.append(
                {
                    "accession_number": acc,
                    "filed_date": f_date,
                    "period_of_report": r_date,
                    "form": form,
                    "amendment_type": cover_info["amendment_type"],
                    "table_entry_total": cover_info["table_entry_total"],
                    "table_value_total": cover_info["table_value_total"],
                    "infotable_doc": cover_info["infotable_doc"],
                }
            )

    if not candidates:
        return []

    # Sort chronologically by filed_date ascending so later amendments appear after originals
    candidates.sort(key=lambda x: (x["filed_date"], x["accession_number"]))

    restatements = [c for c in candidates if c["form"] == "13F-HR/A" and c["amendment_type"] == "RESTATEMENT"]
    if restatements:
        latest_restatement = restatements[-1]
        superseded = [c["accession_number"] for c in candidates if c["accession_number"] != latest_restatement["accession_number"]]
        logger.info(
            "CIK %s (%d-Q%d): Found 13F-HR/A RESTATEMENT %s (filed %s); ignoring superseded filing(s): %s",
            padded_cik,
            year,
            quarter,
            latest_restatement["accession_number"],
            latest_restatement["filed_date"],
            superseded,
        )
        # Remove any superseded raw XML files from raw_dir so they are not parsed alongside the restatement
        for old_acc in superseded:
            old_path = os.path.join(resolved_raw_dir, f"{padded_cik}_{old_acc}.xml")
            if os.path.exists(old_path):
                os.remove(old_path)
                logger.info("Removed superseded raw XML file %s", old_path)
        latest_restatement["superseded_accessions"] = superseded
        return [latest_restatement]

    return candidates


def download_filing_xml(
    cik: str,
    accession_number: str,
    infotable_doc: str | None = None,
    raw_dir: str | None = None,
    user_agent: str | None = None,
) -> str:
    """
    Downloads the information table XML document (not primary_doc.xml) for a filing and saves it to raw_dir.
    
    Filename format is {cik}_{accession_number}.xml.
    
    Args:
        cik (str): Central Index Key of the fund.
        accession_number (str): The accession number of the filing.
        infotable_doc (str | None): Optional pre-resolved information table XML filename.
        raw_dir (str | None): Optional directory for raw XML files (defaults to <DATA_DIR>/raw).
        user_agent (str | None): Optional SEC User-Agent header override.
        
    Returns:
        str: The saved file path.
    """
    resolved_raw_dir = raw_dir or os.path.join(config.DATA_DIR, "raw")
    os.makedirs(resolved_raw_dir, exist_ok=True)
    padded_cik = cik.zfill(10)
    out_path = os.path.join(resolved_raw_dir, f"{padded_cik}_{accession_number}.xml")
    if os.path.exists(out_path):
        logger.info("Filing XML already exists at %s", out_path)
        return out_path

    cik_int = str(int(cik))
    acc_no_hyphens = accession_number.replace("-", "")
    xml_filename = infotable_doc

    if not xml_filename:
        index_url = f"{EDGAR_BASE_URL}/data/{cik_int}/{acc_no_hyphens}/index.json"
        index_data = make_request(index_url, user_agent=user_agent)
        items = index_data.get("directory", {}).get("item", [])
        for item in items:
            name = item.get("name", "")
            if name.endswith(".xml") and "primary_doc" not in name.lower():
                xml_filename = name
                break

    if not xml_filename:
        raise ValueError(f"No information table XML found for {cik} / {accession_number}")

    xml_url = f"{EDGAR_BASE_URL}/data/{cik_int}/{acc_no_hyphens}/{xml_filename}"
    xml_resp = make_request(xml_url, user_agent=user_agent)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_resp["text"])

    logger.info("Saved 13F information table XML (%s) to %s", xml_filename, out_path)
    return out_path


def fetch_all_funds(
    year: int,
    quarter: int,
    raw_dir: str | None = None,
    user_agent: str | None = None,
    metadata_cache_path: str | None = None,
) -> None:
    """
    Orchestrates fetching for all funds in TARGET_FUNDS, calling get_fund_filings then download_filing_xml for each,
    and automatically updating FILING_PERIODS and COVER_PAGE_TOTALS.
    Logs progress throughout the process.
    
    Args:
        year (int): The reporting year.
        quarter (int): The reporting quarter (1-4).
        raw_dir (str | None): Optional directory for raw XML files (defaults to <DATA_DIR>/raw).
        user_agent (str | None): Optional SEC User-Agent header override.
        metadata_cache_path (str | None): Optional path for filing_metadata.json.
    """
    period_str = f"{year}-Q{quarter}"
    for fund_name, cik in TARGET_FUNDS.items():
        logger.info("Fetching %s 13F filings for %s (%s)...", period_str, fund_name, cik)
        try:
            filings = get_fund_filings(cik, year, quarter, raw_dir=raw_dir, user_agent=user_agent)
            for filing in filings:
                acc = filing["accession_number"]
                download_filing_xml(
                    cik,
                    acc,
                    infotable_doc=filing.get("infotable_doc"),
                    raw_dir=raw_dir,
                    user_agent=user_agent,
                )
                _update_filing_periods_config(
                    accession=acc,
                    period=period_str,
                    table_value_total=filing.get("table_value_total"),
                    superseded_accessions=filing.get("superseded_accessions"),
                    metadata_cache_path=metadata_cache_path,
                )
        except Exception as exc:
            logger.error("Failed fetching filings for %s (%s): %s", fund_name, cik, exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    for q in (1, 2):
        fetch_all_funds(year=2026, quarter=q)


