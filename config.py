import os
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# SEC EDGAR Configuration
SEC_BASE_URL = "https://data.sec.gov"
EDGAR_BASE_URL = "https://www.sec.gov/Archives/edgar"
RATE_LIMIT_DELAY = 0.12  # Keeps requests under SEC's 10/sec limit
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "sec_13f_analyzer research@example.com")

# Database Configuration
DATA_DIR = os.getenv("SEC_13F_DATA_DIR", "data")
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "sec_13f.db"))

# OpenFIGI Configuration
OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
OPENFIGI_API_KEY = os.getenv("OPENFIGI_API_KEY", "")


def configure(
    *,
    data_dir: str | None = None,
    db_path: str | None = None,
    user_agent: str | None = None,
    openfigi_api_key: str | None = None,
) -> None:
    """
    Runtime configuration helper allowing external callers importing sec_13f_analyzer
    as a library to override default paths and credentials without relying on a local .env file.
    """
    global DATA_DIR, DB_PATH, SEC_USER_AGENT, OPENFIGI_API_KEY
    if data_dir is not None:
        DATA_DIR = str(data_dir)
        if db_path is None:
            DB_PATH = os.path.join(DATA_DIR, "sec_13f.db")
    if db_path is not None:
        DB_PATH = str(db_path)
    if user_agent is not None:
        SEC_USER_AGENT = str(user_agent)
        os.environ["SEC_USER_AGENT"] = str(user_agent)
    if openfigi_api_key is not None:
        OPENFIGI_API_KEY = str(openfigi_api_key)
        os.environ["OPENFIGI_API_KEY"] = str(openfigi_api_key)

# Target Funds for Analysis (7 verified institutional managers: hedge, conglomerate, pension, SWF)
# Verified against https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<cik>&type=13F-HR
# Note: 0001649339 was Scion Asset Management, LLC; Two Sigma Investments, LP is 0001179392.
TARGET_FUNDS: dict[str, str] = {
    "Berkshire Hathaway": "0001067983",        # Conglomerate
    "Renaissance Technologies": "0001037389",  # Hedge Fund
    "Citadel Advisors": "0001423053",          # Hedge Fund
    "Two Sigma Investments": "0001179392",     # Hedge Fund (fixed from 0001649339)
    "Bridgewater Associates": "0001350694",    # Hedge Fund
    "CalPERS": "0000919079",                   # Public Pension Fund (California Public Employees' Retirement System)
    "Temasek Holdings": "0001021944",          # Sovereign Wealth Fund (Temasek Holdings (Private) Ltd)
}

FUND_TYPES: dict[str, str] = {
    "0001067983": "Conglomerate",
    "0001037389": "Hedge Fund",
    "0001423053": "Hedge Fund",
    "0001179392": "Hedge Fund",
    "0001350694": "Hedge Fund",
    "0000919079": "Public Pension Fund",
    "0001021944": "Sovereign Wealth Fund",
}


# Mapping of active filing accession numbers to reporting periods (updated automatically by fetch_13f.py)
# Note: Citadel 2026-Q2 uses 13F-HR/A full restatement 0001104659-26-104387 (superseding 0001104659-26-097200)
FILING_PERIODS: dict[str, str] = {
    "0001193125-26-226661": "2026-Q1",
    "0001193125-26-352200": "2026-Q2",
    "0001037389-26-000033": "2026-Q1",
    "0001037389-26-000059": "2026-Q2",
    "0001104659-26-062477": "2026-Q1",
    "0001104659-26-104387": "2026-Q2",
    "0000899140-26-000547": "2026-Q1",
    "0000899140-26-000855": "2026-Q2",
    "0001350694-26-000002": "2026-Q1",
    "0001350694-26-000003": "2026-Q2",
    "0000919079-26-000006": "2026-Q1",
    "0000919079-26-000011": "2026-Q2",
    "0001021944-26-000011": "2026-Q1",
    "0001021944-26-000013": "2026-Q2",
}

# Cover-page <tableValueTotal> (in USD) per accession number (verified from primary_doc.xml)
COVER_PAGE_TOTALS: dict[str, int] = {
    "0001193125-26-226661": 263095703570,
    "0001193125-26-352200": 299253556246,
    "0001037389-26-000033": 63929893013,
    "0001037389-26-000059": 72617871974,
    "0001104659-26-062477": 618473172395,
    "0001104659-26-104387": 875011794337,
    "0000899140-26-000547": 123930684213,
    "0000899140-26-000855": 138117670065,
    "0001350694-26-000002": 22404547213,
    "0001350694-26-000003": 24376086530,
    "0000919079-26-000006": 162486869017,
    "0000919079-26-000011": 177384494361,
    "0001021944-26-000011": 30484854533,
    "0001021944-26-000013": 37253810301,
}

# Stock split detection configuration and ground-truth overrides (Q1 2026 -> Q2 2026)
COMMON_SPLIT_FACTORS: tuple[int, ...] = (2, 3, 4, 5, 8, 10, 15, 20, 25, 30)

SPLIT_OVERRIDES: dict[str, float] = {
    "482480100": 10,  # KLA Corp (KLAC): 10-for-1 stock split on June 11, 2026
    "09857L108": 25,  # Booking Holdings (BKNG): 25-for-1 stock split on April 2, 2026
}



