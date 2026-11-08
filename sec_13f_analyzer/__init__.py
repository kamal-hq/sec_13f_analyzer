"""
sec_13f_analyzer: Installable library interface for parsing, mapping, storing, and analyzing SEC 13F filings.
"""

import sys
import config
import run_pipeline as _run_pipeline_mod
from config import (
    COMMON_SPLIT_FACTORS,
    COVER_PAGE_TOTALS,
    DATA_DIR,
    DB_PATH,
    EDGAR_BASE_URL,
    FILING_PERIODS,
    FUND_TYPES,
    OPENFIGI_API_KEY,
    OPENFIGI_URL,
    RATE_LIMIT_DELAY,
    SEC_BASE_URL,
    SEC_USER_AGENT,
    SPLIT_OVERRIDES,
    TARGET_FUNDS,
    configure,
)
from run_pipeline import DISCRETIONARY_FUND_TYPES, run_pipeline
from src import analysis, cusip_mapper, database, fetch_13f, parse_holdings
from src.analysis import (
    export_to_csv,
    get_aum_by_period,
    get_convergence_signals,
    get_etf_convergence_signals,
    get_fund_aum,
    get_fund_concentration,
    get_fund_summary,
    get_new_listing_signals,
    get_new_to_sample_signals,
    get_qoq_exited_positions,
    get_qoq_new_positions,
    get_sector_by_period,
    get_top_holdings_by_aum,
)
from src.cusip_mapper import (
    fetch_from_openfigi,
    load_cusip_cache,
    load_sector_cache,
    map_cusips,
    map_sectors,
    save_cusip_cache,
    save_sector_cache,
    sic_to_sector,
)
from src.database import (
    apply_split_adjustments,
    bulk_insert_holdings,
    create_schema,
    detect_splits,
    get_connection,
    insert_fund,
    insert_holding,
    insert_security,
)
from src.fetch_13f import (
    download_filing_xml,
    fetch_all_funds,
    get_fund_filings,
    make_request,
)
from src.parse_holdings import (
    aggregate_holdings,
    extract_fund_metadata,
    parse_all_raw_files,
    parse_xml_file,
    validate_parsed_data,
)

__version__ = "1.1.0"

# Expose submodules under `sec_13f_analyzer.<module>` for submodule imports
sys.modules[f"{__name__}.config"] = config
sys.modules[f"{__name__}.fetch_13f"] = fetch_13f
sys.modules[f"{__name__}.parse_holdings"] = parse_holdings
sys.modules[f"{__name__}.cusip_mapper"] = cusip_mapper
sys.modules[f"{__name__}.database"] = database
sys.modules[f"{__name__}.analysis"] = analysis
sys.modules[f"{__name__}.run_pipeline"] = _run_pipeline_mod

__all__ = [
    "__version__",
    "config",
    "configure",
    "fetch_13f",
    "parse_holdings",
    "cusip_mapper",
    "database",
    "analysis",
    "run_pipeline",
    "DISCRETIONARY_FUND_TYPES",
    # Config constants
    "SEC_BASE_URL",
    "EDGAR_BASE_URL",
    "RATE_LIMIT_DELAY",
    "SEC_USER_AGENT",
    "DATA_DIR",
    "DB_PATH",
    "OPENFIGI_URL",
    "OPENFIGI_API_KEY",
    "TARGET_FUNDS",
    "FUND_TYPES",
    "FILING_PERIODS",
    "COVER_PAGE_TOTALS",
    "COMMON_SPLIT_FACTORS",
    "SPLIT_OVERRIDES",
    # Fetch
    "make_request",
    "get_fund_filings",
    "download_filing_xml",
    "fetch_all_funds",
    # Parse
    "parse_xml_file",
    "extract_fund_metadata",
    "aggregate_holdings",
    "validate_parsed_data",
    "parse_all_raw_files",
    # CUSIP & Sector Mapping
    "sic_to_sector",
    "load_sector_cache",
    "save_sector_cache",
    "map_sectors",
    "load_cusip_cache",
    "save_cusip_cache",
    "fetch_from_openfigi",
    "map_cusips",
    # Database
    "get_connection",
    "create_schema",
    "insert_fund",
    "insert_security",
    "insert_holding",
    "detect_splits",
    "apply_split_adjustments",
    "bulk_insert_holdings",
    # Analysis
    "get_convergence_signals",
    "get_new_to_sample_signals",
    "get_new_listing_signals",
    "get_etf_convergence_signals",
    "get_qoq_new_positions",
    "get_qoq_exited_positions",
    "get_top_holdings_by_aum",
    "get_fund_concentration",
    "get_aum_by_period",
    "get_fund_summary",
    "get_fund_aum",
    "get_sector_by_period",
    "export_to_csv",
]
