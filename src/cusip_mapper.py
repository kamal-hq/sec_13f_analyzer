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
from config import OPENFIGI_API_KEY, OPENFIGI_URL

logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join("data", "mappings", "cusip_cache.json")
_SESSION = requests.Session()


def load_cusip_cache(cache_path: str = CACHE_PATH) -> dict[str, dict[str, str | None]]:
    """
    Loads existing CUSIP mappings from data/mappings/cusip_cache.json.
    
    Returns:
        dict: The loaded CUSIP mapping. Returns an empty dict if the file does not exist.
    """
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load CUSIP cache from %s: %s", cache_path, exc)
        return {}


def save_cusip_cache(mapping: dict[str, dict[str, str | None]], cache_path: str = CACHE_PATH) -> None:
    """
    Writes the full mapping dict to data/mappings/cusip_cache.json.
    
    Args:
        mapping (dict): The dictionary containing CUSIP mappings.
    """
    cache_dir = os.path.dirname(cache_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
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


def fetch_from_openfigi(cusips: list[str]) -> dict[str, dict[str, str | None]]:
    """
    Sends a batch of up to 100 CUSIPs to the OpenFIGI API.
    
    The batch size limit is 100. Uses a POST request format with a JSON body.
    The API key header is optional but increases rate limits.
    
    Args:
        cusips (list[str]): A list of CUSIPs to fetch mappings for.
        
    Returns:
        dict: A dictionary mapping CUSIPs to their details: {cusip: {ticker, name, security_type}}.
    """
    if not cusips:
        return {}

    batch = cusips[:100]
    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = os.getenv("OPENFIGI_API_KEY", OPENFIGI_API_KEY).strip()
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    return _post_openfigi_batch(batch, headers=headers)


def map_cusips(cusips: list[str]) -> dict[str, dict[str, str | None]]:
    """
    Main entry point for CUSIP mapping.
    
    Loads cache, identifies uncached CUSIPs, fetches them from OpenFIGI in batches,
    updates and saves cache, and returns the full mapping for all input CUSIPs.
    
    Args:
        cusips (list[str]): A list of all CUSIPs needed.
        
    Returns:
        dict: Complete mapping for all requested CUSIPs.
    """
    cache = load_cusip_cache()
    unique_cusips = list(dict.fromkeys(c.strip().upper() for c in cusips if c and str(c).strip()))
    uncached = [c for c in unique_cusips if c not in cache]

    if uncached:
        api_key = os.getenv("OPENFIGI_API_KEY", OPENFIGI_API_KEY).strip()
        # OpenFIGI allows 100 jobs/request with an API key, 10 jobs/request without
        batch_size = 100 if api_key else 10
        delay_sec = 0.25 if api_key else 2.4

        logger.info("Fetching %d uncached CUSIPs from OpenFIGI (batch_size=%d)...", len(uncached), batch_size)
        for i in range(0, len(uncached), batch_size):
            batch = uncached[i : i + batch_size]
            batch_result = fetch_from_openfigi(batch)
            cache.update(batch_result)
            save_cusip_cache(cache)
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

