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
- **Fact_Holdings**: `holding_id`, `fund_id`, `security_id`, `period`, `put_call`, `value_usd`, `shares`, `pct_of_portfolio`, `qoq_change_flag`

## Key Findings (2026-Q1 vs 2026-Q2)

All figures below come directly from SQL queries executed against `data/sec_13f.db`, with the exact source query listed under each claim.

1. **Aggregate Institutional AUM & Option Overlay (`$1.285T` -> `$1.624T` total; `$803.29B` -> `$917.15B` common equity)**:
   Across all 7 institutions (`Berkshire Hathaway`, `Citadel Advisors`, `CalPERS`, `Two Sigma Investments`, `Renaissance Technologies`, `Temasek Holdings`, and `Bridgewater Associates`), total 13F AUM including options rose **+26.40%** from **`$1,284,805,723,954`** in `2026-Q1` to **`$1,624,015,283,814`** in `2026-Q2`. Excluding `Put`/`Call` option contracts, common-equity AUM increased **+14.18%** from **`$803,285,214,028`** in `2026-Q1` to **`$917,153,241,621`** in `2026-Q2`, while reported option notional (`$481,520,509,926` in Q1; `$706,862,042,193` in Q2) accounted for **37.48%** of total 13F value in `2026-Q1` and **43.53%** in `2026-Q2`.
   - *Source query* (`src/analysis.py::get_aum_by_period`):
     ```sql
     SELECT period, COUNT(DISTINCT fund_id) AS fund_count,
            SUM(CASE WHEN value_usd > 0 THEN value_usd ELSE 0 END) AS aum_with_options_usd,
            SUM(CASE WHEN value_usd > 0 AND (put_call IS NULL OR put_call = '') THEN value_usd ELSE 0 END) AS aum_without_options_usd,
            SUM(CASE WHEN value_usd > 0 AND put_call IN ('Put', 'Call') THEN value_usd ELSE 0 END) AS options_aum_usd
     FROM Fact_Holdings GROUP BY period ORDER BY period;
     ```

2. **Full-Universe Smart Money Convergence (`63` qualifying stocks; `6` bought by `5` of `7` funds)**:
   Under the strict share-based buyer definition (common equity only, `qoq_change_flag = 'NEW'` or share count up `>= 10%` QoQ, and dollar value added `shares_added * Q2_price >= $1,000,000`), **`63`** securities were accumulated by **`4` or more** funds in `2026-Q2`. Six securities were bought by **`5` of `7`** funds, led by **`KLAC` (KLA Corp, `+$2,532,371,809` added)**, **`AMD` (Advanced Micro Devices, `+$1,195,133,634` added)**, **`WFC` (Wells Fargo & Co, `+$903,048,556` added)**, **`BKNG` (Booking Holdings, `+$705,311,721` added)**, **`CBRE` (CBRE Group, `+$268,148,933` added)**, and **`FORM` (FormFactor Inc, `+$119,590,856` added)**.
   - *Source query* (`sql/queries.sql` — Query 1 / `get_convergence_signals('2026-Q2', min_funds=4)`):
     ```sql
     -- See Query 1 in sql/queries.sql (HAVING COUNT(DISTINCT qb.fund_id) >= 4)
     ```

3. **Discretionary-Only Convergence (`12` qualifying stocks led by `GOOGL` `+$9.62B` and `GOOG` `+$9.05B`)**:
   Restricting the universe to the 3 non-hedge discretionary institutions (`Conglomerate`, `Public Pension Fund`, `Sovereign Wealth Fund`: `Berkshire Hathaway`, `CalPERS`, and `Temasek Holdings`, requiring `2+` buyers) yields **`12`** convergence signals. Only **`4`** overlap with the 63-stock full list (`KLAC`, `BKNG`, `WMT`, `AMD`), while **`8`** are unique to the discretionary signal list—led by **`GOOGL` (`+$9,618,617,481` added by Berkshire Hathaway & Temasek Holdings)** and **`GOOG` (`+$9,046,385,016` added by Berkshire Hathaway & Temasek Holdings)**.
   - *Source query* (`src/analysis.py::get_convergence_signals('2026-Q2', fund_types=['Conglomerate','Public Pension Fund','Sovereign Wealth Fund'])`):
     ```sql
     -- Query 1 in sql/queries.sql with AND f.fund_type IN ('Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund') HAVING COUNT(DISTINCT qb.fund_id) >= 2
     ```

4. **Sector Coverage & Sector Rotation (`Technology` `+$52.93B` / `+23.10%`; `Energy` `-$5.81B` / `-11.18%`)**:
   SEC EDGAR SIC-to-sector mapping (`data/mappings/sector_cache.json`) covers **89.25%** of common-equity dollar value (**82.07%** of all 13F value including ETF/index options). In `2026-Q2`, common-equity institutional capital rotated most heavily into **`Technology`** (**`+$52,933,434,499`**, from `$229,100,599,115` to `$282,034,033,614`, **+23.10%**) and **`Financials`** (**`+$14,249,245,818`**, from `$153,967,632,776` to `$168,216,878,594`, **+9.25%**), while rotating out of **`Energy`** (**`-$5,808,834,193`**, from `$51,962,745,245` to `$46,153,911,052`, **-11.18%**).
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

## Tech Stack

- Python 3.10+
- requests
- pandas
- lxml
- sqlite3 (built-in)
- python-dotenv

## Disclaimer

13F data is 45 days delayed and for educational purposes only.
