# Power BI Output Data Dictionary (`output/`)

This document defines the schema, data types, and business definitions for the five CSV datasets exported to `output/` for Power BI reporting.

---

## 1. `output/convergence_signals.csv`

Contains **2026-Q2 Smart Money Convergence Signals** across the full 7-fund institutional universe (`min_funds = 4`).
A fund counts as a qualified **buyer** of a security only if:
1. The holding is common equity (`put_call IS NULL OR put_call = ''`, excluding Put/Call option rows),
2. The position was newly initiated (`qoq_change_flag = 'NEW'`) **or** its share count increased by at least **10% QoQ** (`(q2_shares - q1_shares) / q1_shares >= 0.10`), **and**
3. The dollar value of the added shares at Q2 prices (`shares_added * (q2_value_usd / q2_shares)`) is at least **$1,000,000**.

| Column | Type | Description |
| :--- | :--- | :--- |
| `cusip` | `STRING (9)` | 9-character CUSIP (or CINS) security identifier from the SEC Form 13F information table. |
| `ticker` | `STRING` | Exchange ticker symbol mapped via OpenFIGI / SEC EDGAR (`data/mappings/cusip_cache.json`). |
| `company_name` | `STRING` | Canonical issuer name mapped from OpenFIGI with fallback to the 13F XML `<nameOfIssuer>`. |
| `sector` | `STRING` | Broad sector group mapped from the issuer's SEC EDGAR Standard Industrial Classification (SIC) code (`data/mappings/sector_cache.json`), with `'Unknown'` fallback. |
| `funds_buying` | `INTEGER` | Count of distinct institutional funds (`>= 4`) meeting the convergence buyer criteria in `2026-Q2`. |
| `funds` | `STRING` | Alphabetically sorted, comma-separated list of the buying funds' names. |
| `total_dollars_added` | `INTEGER` | Sum of dollar value added (`shares_added * Q2_price`) across all qualified buying funds in USD. |
| `fund_type_breakdown` | `STRING` | Breakdown of qualified buying funds by `Dim_Fund.fund_type` (e.g., `Hedge Fund: 3, Public Pension Fund: 1, Sovereign Wealth Fund: 1`). |

---

## 2. `output/discretionary_signals.csv`

Contains **2026-Q2 Discretionary Smart Money Convergence Signals** restricted to fundamental/long-horizon institutions (`fund_types = ['Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund']`, i.e., Berkshire Hathaway, CalPERS, and Temasek Holdings, where `2+` of the 3 discretionary funds meet the buyer criteria). Uses the same buyer qualification criteria and schema as `convergence_signals.csv`.

| Column | Type | Description |
| :--- | :--- | :--- |
| `cusip` | `STRING (9)` | 9-character CUSIP (or CINS) security identifier. |
| `ticker` | `STRING` | Exchange ticker symbol. |
| `company_name` | `STRING` | Canonical issuer name. |
| `sector` | `STRING` | Broad sector group mapped from the issuer's SEC EDGAR SIC code (`'Unknown'` fallback). |
| `funds_buying` | `INTEGER` | Count of distinct discretionary funds (`>= 2` of 3) meeting the buyer criteria in `2026-Q2`. |
| `funds` | `STRING` | Comma-separated list of the discretionary buying funds. |
| `total_dollars_added` | `INTEGER` | Sum of dollar value added (`shares_added * Q2_price`) across the qualified discretionary buyers in USD. |
| `fund_type_breakdown` | `STRING` | Breakdown of discretionary buying funds by `Dim_Fund.fund_type` (e.g., `Conglomerate: 1, Sovereign Wealth Fund: 1`). |

---

## 3. `output/top_holdings.csv`

Contains the **Top 50 Institutional Equity Holdings in 2026-Q2** ranked by combined common-equity dollar value (`total_aum`) across all 7 funds. Excludes option positions (`Put`/`Call`) and exited placeholder rows (`qoq_change_flag = 'EXITED'`).

| Column | Type | Description |
| :--- | :--- | :--- |
| `cusip` | `STRING (9)` | 9-character CUSIP (or CINS) security identifier. |
| `ticker` | `STRING` | Exchange ticker symbol. |
| `company_name` | `STRING` | Canonical issuer name. |
| `sector` | `STRING` | Broad sector group mapped from the issuer's SEC EDGAR SIC code (`'Unknown'` fallback). |
| `total_aum` | `INTEGER` | Combined common-equity market value in USD across all holding funds in `2026-Q2`. |
| `funds_holding` | `INTEGER` | Number of distinct funds holding an active common-equity position in the security in `2026-Q2`. |
| `holding_funds` | `STRING` | Comma-separated list of the funds holding an active common-equity stake in `2026-Q2`. |

---

## 4. `output/fund_summary.csv`

Contains one row per `(fund, period)` across all 7 funds and both quarters (`2026-Q1` and `2026-Q2`, 14 rows total), summarizing portfolio size with and without options, position counts, top-10 concentration, and quarter-over-quarter activity counts.

| Column | Type | Description |
| :--- | :--- | :--- |
| `fund_name` | `STRING` | Institution name (`Dim_Fund.name`). |
| `cik` | `STRING (10)` | Zero-padded 10-digit SEC Central Index Key (`Dim_Fund.cik`). |
| `fund_type` | `STRING` | Institutional category (`Hedge Fund`, `Conglomerate`, `Public Pension Fund`, or `Sovereign Wealth Fund`). |
| `period` | `STRING` | Reporting period (`2026-Q1` or `2026-Q2`). |
| `active_positions` | `INTEGER` | Total count of active rows (`value_usd > 0`, including both common equity and options). |
| `equity_positions` | `INTEGER` | Count of active non-option holdings (`put_call IS NULL OR put_call = ''`). |
| `option_positions` | `INTEGER` | Count of active option holdings (`put_call IN ('Put', 'Call')`). |
| `total_aum_with_options_usd` | `INTEGER` | Total 13F portfolio market value in USD including options (matches SEC cover-page `<tableValueTotal>`). |
| `equity_aum_without_options_usd` | `INTEGER` | Total 13F portfolio market value in USD excluding `Put` and `Call` option rows. |
| `top_10_concentration_pct` | `FLOAT` | Combined percentage of the fund's total portfolio value held in its top 10 positions (`0.00` to `100.00`). |
| `new_positions_count` | `INTEGER` | Count of holdings with `qoq_change_flag = 'NEW'` (`0` in `2026-Q1` baseline period). |
| `increased_positions_count` | `INTEGER` | Count of holdings with `qoq_change_flag = 'INCREASED'` (`0` in `2026-Q1`). |
| `decreased_positions_count` | `INTEGER` | Count of holdings with `qoq_change_flag = 'DECREASED'` (`0` in `2026-Q1`). |
| `unchanged_positions_count` | `INTEGER` | Count of holdings with `qoq_change_flag = 'UNCHANGED'` (`0` in `2026-Q1`). |
| `exited_positions_count` | `INTEGER` | Count of holdings with `qoq_change_flag = 'EXITED'` (`0` in `2026-Q1`). |

---

## 5. `output/sector_by_period.csv`

Contains institutional AUM aggregated by `(period, sector)` across `2026-Q1` and `2026-Q2`, reporting both common-equity AUM (excluding options) and total AUM (including options).

| Column | Type | Description |
| :--- | :--- | :--- |
| `period` | `STRING` | Reporting period (`2026-Q1` or `2026-Q2`). |
| `sector` | `STRING` | Broad sector group mapped from SEC EDGAR SIC codes (`Technology`, `Financials`, `Healthcare`, `Consumer Discretionary`, `Industrials`, `Communication Services`, `Consumer Staples`, `Energy`, `Utilities`, `Materials`, `Real Estate`, or `Unknown`). |
| `equity_positions` | `INTEGER` | Count of active common-equity holding rows (`put_call IS NULL OR put_call = ''`) in the sector during the period. |
| `funds_holding_equity` | `INTEGER` | Count of distinct funds holding common equity in the sector during the period. |
| `equity_aum_usd` | `INTEGER` | Total common-equity market value in USD (excluding options) for the sector in the period. |
| `pct_of_equity_aum` | `FLOAT` | Percentage of total period common-equity AUM represented by the sector (`0.00` to `100.00`). |
| `total_aum_with_options_usd` | `INTEGER` | Total market value in USD (including `Put` and `Call` options) for the sector in the period. |
| `pct_of_total_aum` | `FLOAT` | Percentage of total period 13F AUM (including options) represented by the sector (`0.00` to `100.00`). |
