# Architecture

## Overview
A star schema design was chosen over flat tables to reduce data redundancy, improve query performance for aggregations (like the Smart Money Convergence query), and logically separate entities. Dim_Fund and Dim_Security store descriptive attributes, while Fact_Holdings stores the quantitative metrics and links the dimensions.

## Data Flow
1. **Source**: SEC EDGAR API provides filing metadata and 13F-HR XML documents.
2. **Fetch**: The `fetch_13f.py` script downloads the filings respecting SEC rate limits.
3. **Parse**: `parse_holdings.py` extracts holdings data from XML files using `lxml` and standardizes it into a DataFrame.
4. **Store**: `database.py` inserts the parsed data into the SQLite star schema.
5. **Analyze & Output**: `analysis.py` queries the database for convergence signals and other metrics, producing outputs like CSVs and markdown research notes.

## Database Design

```sql
-- Dimension table for institutional funds
CREATE TABLE Dim_Fund (
    fund_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Surrogate key
    cik TEXT UNIQUE NOT NULL,                  -- Central Index Key (SEC identifier)
    name TEXT NOT NULL,                        -- Fund name
    fund_type TEXT                             -- Optional fund categorization
);

-- Dimension table for securities
CREATE TABLE Dim_Security (
    security_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Surrogate key
    cusip TEXT UNIQUE NOT NULL,                    -- CUSIP identifier from 13F
    ticker TEXT,                                   -- Mapped ticker symbol
    company_name TEXT,                             -- Issuer name
    security_class TEXT,                           -- 13F titleOfClass (e.g., COM, CAP STK CL A)
    sector TEXT                                    -- Broad industry sector from SEC SIC + overrides
);

-- Fact table for portfolio holdings
CREATE TABLE Fact_Holdings (
    holding_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Surrogate key
    fund_id INTEGER NOT NULL REFERENCES Dim_Fund(fund_id), -- Foreign key to Dim_Fund
    security_id INTEGER NOT NULL REFERENCES Dim_Security(security_id), -- Foreign key to Dim_Security
    period TEXT NOT NULL,                         -- Reporting period (e.g., 2026-Q2)
    put_call TEXT,                                -- Option indicator ('Put', 'Call', or NULL for common equity)
    value_usd INTEGER,                            -- Total value in USD (0 for EXITED rows)
    shares INTEGER,                               -- Split-adjusted number of shares held (0 for EXITED rows)
    pct_of_portfolio REAL,                        -- Percentage of the fund's total portfolio
    qoq_change_flag TEXT CHECK(qoq_change_flag IN ('NEW','INCREASED','DECREASED','EXITED','UNCHANGED')), -- NULL for earliest period
    is_new_listing INTEGER DEFAULT 0,             -- 1 when no fund in the sample held the issuer in the prior period
    UNIQUE(fund_id, security_id, period, put_call)
);

-- View for exited positions
CREATE VIEW View_Exited_Positions AS
SELECT h.holding_id, h.fund_id, f.name AS fund_name, h.security_id,
       s.cusip, s.ticker, s.company_name, s.security_class, s.sector,
       h.period, h.put_call, h.qoq_change_flag
FROM Fact_Holdings h
JOIN Dim_Fund f ON h.fund_id = f.fund_id
JOIN Dim_Security s ON h.security_id = s.security_id
WHERE h.qoq_change_flag = 'EXITED';
```

## CUSIP, Sector & Stock-Split Strategy
- **OpenFIGI Ticker Resolution**: Raw 13F XML filings use 9-character CUSIPs instead of tickers. `src/cusip_mapper.py` resolves CUSIPs in batches via the OpenFIGI API (`v3/mapping`) and persists mappings in `data/mappings/cusip_cache.json`.
- **SEC SIC Sector Classification**: `map_sectors()` resolves each ticker's 4-digit SIC code from the SEC EDGAR submissions API (`CIK{cik}.json`) and caches broad sector mappings in `data/mappings/sector_cache.json`.
- **Stock Split Detection & `yfinance` Confirmation**: `detect_splits()` in `src/database.py` computes median implied per-share prices (`value_usd / shares`) per CUSIP across periods, confirms candidate split factors against `yfinance` split history (cached in `data/mappings/split_cache.json` with `SPLIT_OVERRIDES` in `config.py` taking precedence), and adjusts prior-period shares before computing `qoq_change_flag`.

## Rate Limiting
The SEC strictly enforces a rate limit of 10 requests per second. The pipeline implements a minimum delay (`RATE_LIMIT_DELAY = 0.12`) between requests. A User-Agent header with the developer's name and email is also required by the SEC for all requests to ensure fair usage and accountability.

## Analytical Thesis
The Smart Money Convergence query logic merges multi-class equity shares at the 6-character CUSIP issuer prefix (`SUBSTR(s.cusip, 1, 6)`), excludes options (`put_call IN ('Put', 'Call')`), ETFs/index trusts, and newly established sample positions (`is_new_listing = 1`), and identifies operating issuers where `>= 4` funds (`>= 2` in the 3-fund discretionary subset) qualify as buyers (`qoq_change_flag = 'NEW'` or split-adjusted shares up `>= 10%` QoQ, and `added_value_usd >= $1,000,000` at Q2 prices).
