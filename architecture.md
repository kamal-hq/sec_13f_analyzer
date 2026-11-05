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
    sector TEXT                                    -- Industry sector
);

-- Fact table for portfolio holdings
CREATE TABLE Fact_Holdings (
    holding_id INTEGER PRIMARY KEY AUTOINCREMENT, -- Surrogate key
    fund_id INTEGER NOT NULL REFERENCES Dim_Fund(fund_id), -- Foreign key to Dim_Fund
    security_id INTEGER NOT NULL REFERENCES Dim_Security(security_id), -- Foreign key to Dim_Security
    period TEXT NOT NULL,                         -- Reporting period (e.g., 2024-Q2)
    value_usd INTEGER,                            -- Total value in USD
    shares INTEGER,                               -- Number of shares held
    pct_of_portfolio REAL,                        -- Percentage of the fund's total portfolio
    qoq_change_flag TEXT CHECK(qoq_change_flag IN ('NEW','INCREASED','DECREASED','EXITED','UNCHANGED')) -- Quarter-over-quarter change status
);
```

## CUSIP Mapping Strategy
Raw 13F XML filings use CUSIPs instead of tickers to identify securities. CUSIPs are standard but not user-friendly for analysis. OpenFIGI solves this by mapping CUSIPs to tickers. A local JSON cache is used to store previously mapped CUSIPs, avoiding repeat API calls and minimizing rate limit issues.

## Rate Limiting
The SEC strictly enforces a rate limit of 10 requests per second. The pipeline implements a minimum delay (`RATE_LIMIT_DELAY = 0.12`) between requests. A User-Agent header with the developer's name and email is also required by the SEC for all requests to ensure fair usage and accountability.

## Analytical Thesis
The Smart Money Convergence query logic groups facts by `security_id` (or ticker) and uses a `HAVING COUNT(DISTINCT fund_id) >= 3` clause. By filtering for `qoq_change_flag IN ('NEW', 'INCREASED')`, it identifies securities that at least three major institutions independently bought into or accumulated further during the same quarter, comparing current quarter holdings vs the previous quarter.
