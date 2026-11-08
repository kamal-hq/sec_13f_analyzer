"""
Maps CUSIP identifiers to human-readable tickers and company names using the OpenFIGI API,
with local JSON caching to avoid redundant API calls.
"""

import json
import logging
import os
import time
from typing import Any
import requests
import config
from config import OPENFIGI_API_KEY, OPENFIGI_URL, RATE_LIMIT_DELAY, SEC_BASE_URL, SEC_USER_AGENT

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join("data", "mappings", "cusip_cache.json")
SECTOR_CACHE_PATH = os.path.join("data", "mappings", "sector_cache.json")
_SESSION = requests.Session()


def sic_to_sector(sic: str | int | None) -> str:
    """
    Maps a 4-digit SEC Standard Industrial Classification (SIC) code to a broad sector group,
    with 'Unknown' as fallback.
    """
    if sic is None or str(sic).strip() == "":
        return "Unknown"
    try:
        code = int(str(sic).strip())
    except ValueError:
        return "Unknown"

    if code <= 0:
        return "Unknown"
    # Energy: Oil & Gas extraction (1300-1389), Petroleum refining (2900-2999), Pipelines (4600-4699), Natural gas transmission (4920-4925)
    if (1300 <= code <= 1389) or (2900 <= code <= 2999) or (4600 <= code <= 4699) or (4920 <= code <= 4925):
        return "Energy"
    # Materials: Mining (1000-1299, 1400-1499), Wood/Paper (2400-2499, 2600-2699),
    # Chemicals ex-drugs/cosmetics (2800-2829, 2850-2899), Plastics/Glass/Metals/Cans (3050-3089, 3200-3419)
    if (
        (1000 <= code <= 1299)
        or (1400 <= code <= 1499)
        or (2400 <= code <= 2499)
        or (2600 <= code <= 2699)
        or (2800 <= code <= 2829)
        or (2850 <= code <= 2899)
        or (3050 <= code <= 3089)
        or (3200 <= code <= 3419)
    ):
        return "Materials"
    # Healthcare: Drugs/Biologicals (2830-2836), Medical instruments (3840-3851), Medical plans (6324), Health services (8000-8099)
    if (2830 <= code <= 2836) or (3840 <= code <= 3851) or code == 6324 or (8000 <= code <= 8099):
        return "Healthcare"
    # Technology: Semiconductor machinery (3559), Computers (3570-3579), Comms equipment & semiconductors (3660-3679),
    # Measuring/Optical/Test instruments (3820-3829), Software/IT (7370-7379)
    if code == 3559 or (3570 <= code <= 3579) or (3660 <= code <= 3679) or (3820 <= code <= 3829) or (7370 <= code <= 7379):
        return "Technology"
    # Communication Services: Publishing (2711-2741), Telecom/Broadcast (4800-4899), Advertising (7310-7319), Motion pictures (7800-7899)
    if (2711 <= code <= 2741) or (4800 <= code <= 4899) or (7310 <= code <= 7319) or (7800 <= code <= 7899):
        return "Communication Services"
    # Utilities: Electric, gas, water & sanitary services (4900-4999, except 4920-4925)
    if 4900 <= code <= 4999:
        return "Utilities"
    # Real Estate: Real estate operators/developers (6500-6599) and REITs (6798)
    if (6500 <= code <= 6599) or code == 6798:
        return "Real Estate"
    # Financials: Banks, credit, brokers, insurance, investment offices (6000-6799, except 6324, 6500-6599, 6798) & Credit agencies (7320)
    if (6000 <= code <= 6799) or code == 7320:
        return "Financials"
    # Consumer Staples: Agriculture (0100-0999), Food/Beverage/Tobacco (2000-2199), Soaps/Cosmetics (2840-2844),
    # Grocery/Beer wholesale & retail (5140-5149, 5180-5189, 5331, 5400-5499, 5912)
    if (
        (100 <= code <= 999)
        or (2000 <= code <= 2199)
        or (2840 <= code <= 2844)
        or (5140 <= code <= 5149)
        or (5180 <= code <= 5189)
        or code in (5331, 5912)
        or (5400 <= code <= 5499)
    ):
        return "Consumer Staples"
    # Consumer Discretionary: Homebuilders (1520-1531), Apparel/Furniture/Footwear (2200-2399, 2500-2599, 3011-3049, 3100-3199),
    # Appliances/Audio (3630-3659), Autos (3711-3716, 3751), Toys/Misc (3900-3999), Travel agencies (4700), Retail/Restaurants/Hotels/Leisure
    if (
        (1520 <= code <= 1531)
        or (2200 <= code <= 2399)
        or (2500 <= code <= 2599)
        or (3011 <= code <= 3049)
        or (3100 <= code <= 3199)
        or (3630 <= code <= 3659)
        or (3711 <= code <= 3716)
        or code in (3751, 4700)
        or (3900 <= code <= 3999)
        or (5010 <= code <= 5015)
        or (5130 <= code <= 5139)
        or (5200 <= code <= 5999)
        or (7000 <= code <= 7299)
        or (7500 <= code <= 7599)
        or (7900 <= code <= 7999)
        or (8200 <= code <= 8299)
    ):
        return "Consumer Discretionary"
    # Industrials: Heavy construction, machinery, electrical apparatus, aerospace/defense/rail, instruments, transportation, wholesale, business/engineering services
    if (
        (1500 <= code <= 1799)
        or (2700 <= code <= 2799)
        or (3400 <= code <= 3899)
        or (4000 <= code <= 4799)
        or (5000 <= code <= 5199)
        or (7300 <= code <= 7699)
        or (8100 <= code <= 8999)
    ):
        return "Industrials"
    return "Unknown"


# Overrides for issuers where legacy 1987 SEC SIC codes (e.g. 7389 Business Services, 2670 Paper Products, 4400 Water Transport)
# misclassify modern GICS sectors.
TICKER_SECTOR_OVERRIDES: dict[str, str] = {
    "BKNG": "Consumer Discretionary",
    "ABNB": "Consumer Discretionary",
    "EXPE": "Consumer Discretionary",
    "CCL": "Consumer Discretionary",
    "RCL": "Consumer Discretionary",
    "NCLH": "Consumer Discretionary",
    "FIVE": "Consumer Discretionary",
    "KMB": "Consumer Staples",
    "CASY": "Consumer Staples",
    "ACN": "Technology",
    "IT": "Technology",
    "NOVT": "Technology",
    "V": "Financials",
    "MA": "Financials",
    "PYPL": "Financials",
    "FIS": "Financials",
    "FI": "Financials",
    "GPN": "Financials",
}


def load_sector_cache(cache_path: str | None = None) -> dict[str, dict[str, Any]]:
    """Loads existing ticker -> SIC/sector mappings from sector_cache.json."""
    resolved_path = cache_path or os.path.join(config.DATA_DIR, "mappings", "sector_cache.json")
    if not os.path.exists(resolved_path):
        return {}
    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load sector cache from %s: %s", resolved_path, exc)
        return {}


def save_sector_cache(mapping: dict[str, dict[str, Any]], cache_path: str | None = None) -> None:
    """Writes the full sector cache dict to sector_cache.json."""
    resolved_path = cache_path or os.path.join(config.DATA_DIR, "mappings", "sector_cache.json")
    cache_dir = os.path.dirname(resolved_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    with open(resolved_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)


def map_sectors(
    tickers: list[str],
    fetch_uncached: bool = False,
    cache_path: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str]:
    """
    Maps tickers to broad sector groups using the SEC submissions API SIC code cached in
    data/mappings/sector_cache.json, with 'Unknown' as fallback.
    """
    sector_cache = load_sector_cache(cache_path=cache_path)
    unique_tickers = [str(t).strip().upper() for t in dict.fromkeys(tickers) if t and str(t).strip() and str(t) != "None"]

    # Ensure every entry in sector_cache has its computed broad sector field
    updated = False
    for t, entry in list(sector_cache.items()):
        if isinstance(entry, dict):
            desired = TICKER_SECTOR_OVERRIDES.get(t) or sic_to_sector(entry.get("sic"))
            if entry.get("sector") != desired:
                entry["sector"] = desired
                updated = True
        elif isinstance(entry, str):
            sector_cache[t] = {"sic": None, "sic_description": None, "sector": TICKER_SECTOR_OVERRIDES.get(t, entry)}
            updated = True

    if fetch_uncached:
        uncached = [t for t in unique_tickers if t not in sector_cache]
        if uncached:
            resolved_ua = user_agent or os.getenv("SEC_USER_AGENT", config.SEC_USER_AGENT)
            headers = {"User-Agent": resolved_ua, "Accept-Encoding": "gzip, deflate"}
            try:
                resp = _SESSION.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=30)
                resp.raise_for_status()
                ticker_to_cik = {
                    item["ticker"].upper(): str(item["cik_str"]).zfill(10)
                    for item in resp.json().values()
                }
                for t in uncached:
                    cik = ticker_to_cik.get(t)
                    if not cik:
                        continue
                    time.sleep(RATE_LIMIT_DELAY)
                    sub = _SESSION.get(f"{SEC_BASE_URL}/submissions/CIK{cik}.json", headers=headers, timeout=20)
                    if sub.status_code == 200:
                        d = sub.json()
                        sic = d.get("sic")
                        sector_cache[t] = {
                            "cik": cik,
                            "sic": sic,
                            "sic_description": d.get("sicDescription"),
                            "sector": TICKER_SECTOR_OVERRIDES.get(t) or sic_to_sector(sic),
                        }
                        updated = True
            except requests.RequestException as exc:
                logger.warning("Could not fetch uncached SEC SIC codes: %s", exc)

    if updated:
        save_sector_cache(sector_cache, cache_path=cache_path)

    result: dict[str, str] = {}
    for t in unique_tickers:
        if t in TICKER_SECTOR_OVERRIDES:
            result[t] = TICKER_SECTOR_OVERRIDES[t]
            continue
        entry = sector_cache.get(t)
        if isinstance(entry, dict):
            sec = entry.get("sector") or sic_to_sector(entry.get("sic"))
            result[t] = sec if sec else "Unknown"
        elif isinstance(entry, str) and entry:
            result[t] = entry
        else:
            result[t] = "Unknown"
    return result


def load_cusip_cache(cache_path: str | None = None) -> dict[str, dict[str, str | None]]:
    """
    Loads existing CUSIP mappings from data/mappings/cusip_cache.json.
    
    Returns:
        dict: The loaded CUSIP mapping. Returns an empty dict if the file does not exist.
    """
    resolved_path = cache_path or os.path.join(config.DATA_DIR, "mappings", "cusip_cache.json")
    if not os.path.exists(resolved_path):
        return {}
    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load CUSIP cache from %s: %s", resolved_path, exc)
        return {}


def save_cusip_cache(mapping: dict[str, dict[str, str | None]], cache_path: str | None = None) -> None:
    """
    Writes the full mapping dict to data/mappings/cusip_cache.json.
    
    Args:
        mapping (dict): The dictionary containing CUSIP mappings.
    """
    resolved_path = cache_path or os.path.join(config.DATA_DIR, "mappings", "cusip_cache.json")
    cache_dir = os.path.dirname(resolved_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    with open(resolved_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)


def _post_openfigi_batch(
    batch: list[str],
    headers: dict[str, str],
    max_retries: int = 5,
) -> dict[str, dict[str, str | None]]:
    """Sends a single POST request to OpenFIGI with exponential backoff on HTTP 429."""
    # 9-char identifiers starting with a letter are international CINS codes in OpenFIGI
    payload = [
        {
            "idType": "ID_CINS" if (c and c[0].isalpha()) else "ID_CUSIP",
            "idValue": c,
            "exchCode": "US",
        }
        for c in batch
    ]

    for attempt in range(max_retries):
        try:
            response = _SESSION.post(OPENFIGI_URL, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            wait = 2 ** attempt
            logger.warning("OpenFIGI network error (attempt %d/%d): %s; retrying in %ds", attempt + 1, max_retries, exc, wait)
            time.sleep(wait)
            continue

        if response.status_code == 429:
            # Respect server Retry-After / ratelimit-reset header when provided, else exponential backoff
            reset_hdr = response.headers.get("Retry-After") or response.headers.get("ratelimit-reset")
            wait = int(reset_hdr) + 1 if (reset_hdr and str(reset_hdr).isdigit()) else (2 ** (attempt + 1))
            logger.warning("OpenFIGI 429 rate limit hit; backing off for %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
            time.sleep(wait)
            continue

        if response.status_code == 413 and len(batch) > 10:
            # Unauthenticated OpenFIGI requests only allow 10 mapping jobs per request
            logger.info("OpenFIGI returned 413 without API key; splitting %d CUSIPs into 10-item sub-batches.", len(batch))
            combined: dict[str, dict[str, str | None]] = {}
            for i in range(0, len(batch), 10):
                combined.update(_post_openfigi_batch(batch[i : i + 10], headers=headers, max_retries=max_retries))
                if i + 10 < len(batch):
                    time.sleep(0.25)
            return combined

        response.raise_for_status()
        items: list[dict[str, Any]] = response.json()

        result: dict[str, dict[str, str | None]] = {}
        for cusip, item in zip(batch, items):
            matches = item.get("data", []) if isinstance(item, dict) else []
            if matches:
                best = matches[0]
                result[cusip] = {
                    "ticker": best.get("ticker"),
                    "name": best.get("name"),
                    "security_type": best.get("securityType"),
                }
            else:
                result[cusip] = {
                    "ticker": None,
                    "name": None,
                    "security_type": None,
                }
        return result

    logger.error("Exhausted retries for OpenFIGI batch of %d CUSIPs.", len(batch))
    return {c: {"ticker": None, "name": None, "security_type": None} for c in batch}


def fetch_from_openfigi(cusips: list[str], api_key: str | None = None) -> dict[str, dict[str, str | None]]:
    """
    Sends a batch of up to 100 CUSIPs to the OpenFIGI API.
    
    The batch size limit is 100. Uses a POST request format with a JSON body.
    The API key header is optional but increases rate limits.
    
    Args:
        cusips (list[str]): A list of CUSIPs to fetch mappings for.
        api_key (str | None): Optional OpenFIGI API key override.
        
    Returns:
        dict: A dictionary mapping CUSIPs to their details: {cusip: {ticker, name, security_type}}.
    """
    if not cusips:
        return {}

    batch = cusips[:100]
    headers: dict[str, str] = {"Content-Type": "application/json"}
    resolved_key = (api_key if api_key is not None else os.getenv("OPENFIGI_API_KEY", config.OPENFIGI_API_KEY)).strip()
    if resolved_key:
        headers["X-OPENFIGI-APIKEY"] = resolved_key

    return _post_openfigi_batch(batch, headers=headers)


def map_cusips(
    cusips: list[str],
    cache_path: str | None = None,
    api_key: str | None = None,
) -> dict[str, dict[str, str | None]]:
    """
    Main entry point for CUSIP mapping.
    
    Loads cache, identifies uncached CUSIPs, fetches them from OpenFIGI in batches,
    updates and saves cache, and returns the full mapping for all input CUSIPs.
    
    Args:
        cusips (list[str]): A list of all CUSIPs needed.
        cache_path (str | None): Optional path to cusip_cache.json.
        api_key (str | None): Optional OpenFIGI API key override.
        
    Returns:
        dict: Complete mapping for all requested CUSIPs.
    """
    cache = load_cusip_cache(cache_path=cache_path)
    unique_cusips = list(dict.fromkeys(c.strip().upper() for c in cusips if c and str(c).strip()))
    uncached = [c for c in unique_cusips if c not in cache]

    if uncached:
        resolved_key = (api_key if api_key is not None else os.getenv("OPENFIGI_API_KEY", config.OPENFIGI_API_KEY)).strip()
        # OpenFIGI allows 100 jobs/request with an API key, 10 jobs/request without
        batch_size = 100 if resolved_key else 10
        delay_sec = 0.25 if resolved_key else 2.4

        logger.info("Fetching %d uncached CUSIPs from OpenFIGI (batch_size=%d)...", len(uncached), batch_size)
        for i in range(0, len(uncached), batch_size):
            batch = uncached[i : i + batch_size]
            batch_result = fetch_from_openfigi(batch, api_key=api_key)
            cache.update(batch_result)
            save_cusip_cache(cache, cache_path=cache_path)
            if i + batch_size < len(uncached):
                time.sleep(delay_sec)
    else:
        logger.info("All %d unique CUSIPs found in local cache.", len(unique_cusips))

    return {
        c: cache.get(c, {"ticker": None, "name": None, "security_type": None})
        for c in unique_cusips
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sample_cusips = ["037833100"]  # Example Apple CUSIP
    print(map_cusips(sample_cusips))


