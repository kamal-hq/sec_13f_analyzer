# sec_13f_analyzer

**Tracking institutional consensus buying signals from SEC 13F filings**

## Project Overview

The Smart Money Convergence thesis aims to find stocks that 3 or more major institutions independently initiated or increased positions in during the same quarter. By analyzing SEC 13F filings from top-tier institutional investors, this project identifies consensus buying signals that may indicate high-conviction institutional accumulation.

## Architecture

The system follows a 5-layer pipeline: Source → Fetch → Parse → Store → Analyze → Output.

## Data Pipeline

- **fetch_13f.py**: Fetches 13F-HR filing metadata and XML files from SEC EDGAR.
- **parse_holdings.py**: Parses downloaded XML files and extracts individual holding records.
- **cusip_mapper.py**: Maps CUSIP identifiers to human-readable tickers using the OpenFIGI API.
- **database.py**: Handles SQLite database operations including schema creation and data insertion.
- **analysis.py**: Queries the database to produce the Smart Money Convergence analysis and outputs.

## Installation

1. Clone the repository.
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment.
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in the required values (SEC User-Agent).

## Usage

1. Run `python src/fetch_13f.py` first OR manually place XMLs in `data/raw/`.
2. Run `python src/parse_holdings.py`.
3. Run `python src/database.py`.
4. Run `python src/analysis.py` in sequence.

## Database Schema

- **Dim_Fund**: `fund_id`, `cik`, `name`, `fund_type`
- **Dim_Security**: `security_id`, `cusip`, `ticker`, `company_name`, `security_class`, `sector`
- **Fact_Holdings**: `holding_id`, `fund_id`, `security_id`, `period`, `put_call`, `value_usd`, `shares`, `pct_of_portfolio`, `qoq_change_flag`, `is_new_listing`

## Key Findings (2026-Q1 vs 2026-Q2)

All figures below come directly from SQL queries executed against `data/sec_13f.db`, with the exact source query listed under each claim.

1. **Broad Convergence Is Dominated by Hedge-Fund-Only Signals; Discretionary Convergence (`3`-Fund Sample) Is More Informative**:
   Because 4 of the 7 institutions in our universe are high-breadth hedge funds (`Citadel Advisors`, `Two Sigma Investments`, `Renaissance Technologies`, and `Bridgewater Associates`), **`31` of the `56`** full-universe convergence signals (`min_funds = 4`, operating common equities with prior-quarter holders) are **hedge-fund-only** (`Hedge Fund: 4`) signals, and **all `56`** require at least 2 hedge funds. Isolating the discretionary long-horizon subset (`Conglomerate`, `Public Pension Fund`, `Sovereign Wealth Fund`—noting that **the discretionary sample is only `3` funds**: `Berkshire Hathaway`, `CalPERS`, and `Temasek Holdings`) surfaces **`9`** issuer-level convergence signals (`2+` of `3` buying), **`7` of which do not appear in the 56-stock full-universe list**, led by merged **`GOOGL/GOOG` (`ALPHABET INC`, `+$18,665,002,497` added across Class A and Class C by `Berkshire Hathaway` and `Temasek Holdings`)** and **`C` (`CITIGROUP INC`, `+$226,493,349` added by `CalPERS` and `Temasek Holdings`)**.
   - *Source queries* (`sql/queries.sql` — Query 1 & `src/analysis.py::get_convergence_signals`):
     ```sql
     -- Full Universe (56 signals): Query 1 in sql/queries.sql (HAVING COUNT(DISTINCT qb.fund_id) >= 4)
     -- Discretionary Subset (9 signals): Query 1 with AND f.fund_type IN ('Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund') HAVING COUNT(DISTINCT qb.fund_id) >= 2
     ```

2. **Full-Universe Smart Money Convergence (`56` Seasoned Issuers) & Separate "New to the sample (no prior-quarter holders)" Table (`SPCX` `#1` at `+$2.86B`)**:
   Under the strict split-adjusted, issuer-merged (`SUBSTR(cusip, 1, 6)`) buyer definition (operating common equity only, excluding options, ETFs/index trusts, and "New to the sample (no prior-quarter holders)" rows where `is_new_listing = 1`; `qoq_change_flag = 'NEW'` or split-adjusted share count up `>= 10%` QoQ; and `added_value_usd >= $1,000,000`), **`56`** seasoned issuers were accumulated by **`4` or more** funds in `2026-Q2`. Four issuers were bought by **`5` of `7`** funds: **`AMD` (`+$1,195,133,634` added)**, **`WFC` (`+$903,048,556` added)**, **`CBRE` (`+$268,148,933` added)**, and **`FORM` (`+$119,590,856` added)**, followed among 4-buyer stocks by **`STX` (`+$1,333,294,180` added)** and **`NFLX` (`+$1,058,109,711` added)**. Newly established positions where **no fund in the sample** held the issuer in `2026-Q1` (`is_new_listing = 1`) are separated into the **"New to the sample (no prior-quarter holders)"** table (`output/new_positions_signals.csv` via `get_new_to_sample_signals`), led by newly established positions in **`SPCX` (`SPACE EXPLORATION TECHNOLOGIES CORP`, `4` funds buying, `+$2,861,656,740` added)** and **`VGNT` (`VERSIGENT PLC`, `4` funds buying, `+$47,816,706` added)**. Confirming auto-detected stock splits against `yfinance` split history (cached in `data/mappings/split_cache.json`) ensured that only **`3` confirmed splits** (`BKNG` 25-for-1, `KLAC` 10-for-1, `CVNA` 5-for-1, adjusting `25` Q1 rows) were applied, while **`7` unconfirmed price-ratio candidates** (`PSIG`, `LPCN`, `CURX`, `500767330`, `SLNH`, `TDUP`, `TMCI`) were logged and skipped.
   - *Source queries* (`sql/queries.sql` — Query 1; `src/analysis.py::get_new_to_sample_signals`):
     ```sql
     -- Seasoned Convergence (56 signals): Query 1 in sql/queries.sql (WHERE COALESCE(h.is_new_listing, 0) = 0)
     -- New to the sample (no prior-quarter holders) (4 signals): get_new_to_sample_signals('2026-Q2', min_funds=3) (WHERE h.is_new_listing = 1)
     ```

3. **Aggregate Institutional AUM & Option Overlay (`$1.285T` -> `$1.624T` total; `$803.29B` -> `$917.15B` common equity)**:
   Across all 7 institutions (`Berkshire Hathaway`, `Citadel Advisors`, `CalPERS`, `Two Sigma Investments`, `Renaissance Technologies`, `Temasek Holdings`, and `Bridgewater Associates`), total 13F AUM including options rose **+26.40%** from **`$1,284,805,723,954`** in `2026-Q1` to **`$1,624,015,283,814`** in `2026-Q2`. Excluding `Put`/`Call` option contracts, common-equity AUM increased **+14.18%** from **`$803,285,214,028`** in `2026-Q1` to **`$917,153,241,621`** in `2026-Q2`, while reported option notional (`$481,520,509,926` in Q1; `$706,862,042,193` in Q2) accounted for **37.48%** of total 13F value in `2026-Q1` and **43.53%** in `2026-Q2`.
   - *Source query* (`src/analysis.py::get_aum_by_period`):
     ```sql
     SELECT period, COUNT(DISTINCT fund_id) AS fund_count,
            SUM(CASE WHEN value_usd > 0 THEN value_usd ELSE 0 END) AS aum_with_options_usd,
            SUM(CASE WHEN value_usd > 0 AND (put_call IS NULL OR put_call = '') THEN value_usd ELSE 0 END) AS aum_without_options_usd,
            SUM(CASE WHEN value_usd > 0 AND put_call IN ('Put', 'Call') THEN value_usd ELSE 0 END) AS options_aum_usd
     FROM Fact_Holdings GROUP BY period ORDER BY period;
     ```

4. **Sector Coverage & Sector Rotation (`Technology` `+$53.22B` / `+23.13%`; `Energy` `-$5.81B` / `-11.18%`)**:
   SEC EDGAR SIC-to-sector mapping (`data/mappings/sector_cache.json`) covers **89.42%** of common-equity dollar value (**82.25%** of all 13F value including ETF/index options). In `2026-Q2`, common-equity institutional capital rotated most heavily into **`Technology`** (**`+$53,218,012,069`**, from `$230,064,460,040` to `$283,282,472,109`, **+23.13%**) and **`Financials`** (**`+$14,679,664,217`**, from `$162,164,172,175` to `$176,843,836,392`, **+9.05%**), while rotating out of **`Energy`** (**`-$5,808,834,193`**, from `$51,962,745,245` to `$46,153,911,052`, **-11.18%**).
   - *Source query* (`sql/queries.sql` — Query 6):
     ```sql
     SELECT s.sector,
            SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END) AS q1_equity_aum_usd,
            SUM(CASE WHEN h.period = '2026-Q2' THEN h.value_usd ELSE 0 END) AS q2_equity_aum_usd,
            (SUM(CASE WHEN h.period = '2026-Q2' THEN h.value_usd ELSE 0 END) -
             SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END)) AS qoq_dollar_change_usd
     FROM Fact_Holdings h JOIN Dim_Security s ON h.security_id = s.security_id
     WHERE h.period IN ('2026-Q1', '2026-Q2') AND (h.put_call IS NULL OR h.put_call = '') AND h.value_usd > 0
     GROUP BY s.sector ORDER BY qoq_dollar_change_usd DESC;
     ```

5. **Portfolio Concentration & Top Consensus Holdings (`AAPL` `#1` at `$78.56B`; Berkshire Top-10 at `88.47%` vs Two Sigma at `8.28%`)**:
   Across all 7 funds in `2026-Q2`, **`AAPL` (`$78,557,728,582`, held by all `7` funds)**, **`AXP` (`$51,771,457,190`, `6` funds)**, and **`GOOGL` (`$38,177,090,936`, `7` funds)** rank as the largest combined common-equity holdings. Top-10 portfolio concentration ranges from **88.47%** at `Berkshire Hathaway` (`29` active positions, `$299,253,556,246` AUM) and **51.42%** at `Temasek Holdings` (`196` active positions, `$37,253,810,301` AUM) down to **8.28%** at `Two Sigma Investments` (`5,017` active positions, `$138,117,670,065` AUM) and **12.01%** at `Renaissance Technologies` (`3,139` active positions, `$72,617,871,974` AUM).
   - *Source queries* (`sql/queries.sql` — Query 4 & Query 5; `src/analysis.py::get_fund_summary`):
     ```sql
     -- See Query 4 (Top Holdings by Total Institutional AUM) and Query 5 (Fund Concentration) in sql/queries.sql
     ```

## Limitations

1. **Long-Only Disclosure**: Form 13F only requires reporting of long positions in Section 13(f) US exchange-traded equities and listed `Put`/`Call` options. It omits short equity positions, total-return swaps, OTC derivatives, and non-US local shares—meaning a reported long equity stake may be partially or fully offset by an unreported short leg.
2. **45-Day Reporting Delay**: Institutional managers have up to 45 calendar days after quarter-end to file Form 13F-HR. High-turnover managers may have already resized or exited quarter-end positions by the time the filing becomes public.
3. **Hedge-Fund-Only Turnover Noise & Small Discretionary Sample Size (`3` Funds)**: Share increases in hedge-fund-only signals (`Citadel Advisors`, `Two Sigma Investments`, `Renaissance Technologies`, `Bridgewater Associates`) frequently reflect factor rebalancing, market-making inventory, or delta-hedging against options books (`$700.88B` of option notional at Citadel in `2026-Q2`) rather than fundamental directional conviction. Isolating the discretionary subset (`output/discretionary_signals.csv`) provides a cleaner fundamental signal, though users should note that the discretionary sample in this study comprises only **3 funds** (`Berkshire Hathaway`, `CalPERS`, and `Temasek Holdings`).
4. **No Forward-Return Test & Q2 Price Valuation**: No forward-return test is performed, so this analysis describes institutional behavior rather than predictive alpha; additionally, dollars added use Q2 period-end implied prices (`shares_added * Q2_price`).

## Tech Stack

- Python 3.10+
- requests
- pandas
- lxml
- yfinance
- sqlite3 (built-in)
- python-dotenv

## Disclaimer

13F data is 45 days delayed and for educational purposes only.

