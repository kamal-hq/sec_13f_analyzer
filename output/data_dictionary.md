# Power BI Output Data Dictionary (`output/` & `dashboard/data/`)

This document defines the schema, data types, and business definitions for the seven CSV datasets exported to `output/` (gitignored) and copied into `dashboard/data/` (tracked in Git) for Power BI reporting.

---

## 1. `output/convergence_signals.csv` (`dashboard/data/convergence_signals.csv`)

Contains **2026-Q2 Smart Money Convergence Signals** across the full 7-fund institutional universe (`min_funds = 4`), merged at the 6-character CUSIP issuer level (e.g., `GOOGL` + `GOOG` merged into one `ALPHABET INC` row).
A fund counts as a qualified **buyer** of an operating common-equity security only if:
1. The holding is operating common equity (`put_call IS NULL OR put_call = ''`, excluding options, notes/preferreds/warrants, ETFs/index trusts, and "New to the sample (no prior-quarter holders)" positions where `is_new_listing = 1`),
2. The position was newly initiated (`qoq_change_flag = 'NEW'`) **or** its split-adjusted share count increased by at least **10% QoQ** (`(q2_shares - q1_split_adj_shares) / q1_split_adj_shares >= 0.10`), **and**
3. The dollar value of the added shares at Q2 prices (`shares_added * (q2_value_usd / q2_shares)`) is at least **$1,000,000**.
4. Multiple share classes of the same issuer (`SUBSTR(cusip, 1, 6)`) are merged into a single row: `total_dollars_added` is summed across share classes and each buying fund is counted once.

| Column | Type | Description |
| :--- | :--- | :--- |
| `cusip` | `STRING` | 9-character CUSIP (or `/`-delimited CUSIPs when multiple share classes of the same issuer are merged, e.g., `02079K305/02079K107`). |
| `ticker` | `STRING` | Exchange ticker symbol (or `/`-delimited tickers when multiple share classes are merged, e.g., `GOOGL/GOOG`). |
| `company_name` | `STRING` | Canonical issuer name mapped from OpenFIGI with fallback to the 13F XML `<nameOfIssuer>`. |
| `sector` | `STRING` | Broad sector group mapped from the issuer's SEC EDGAR Standard Industrial Classification (SIC) code (`data/mappings/sector_cache.json`), with `'Unknown'` fallback. |
| `is_new_listing` | `INTEGER` | `1` if no fund in the sample held the security in the prior period (`2026-Q1`); `0` otherwise. Main convergence tables exclude `is_new_listing = 1` (which are reported in the separate "New to the sample (no prior-quarter holders)" table `output/new_positions_signals.csv`). |
| `funds_buying` | `INTEGER` | Count of distinct institutional funds (`>= 4`) meeting the convergence buyer criteria in `2026-Q2` (each fund counted once per issuer). |
| `hedge_fund_buyers` | `INTEGER` | Count of distinct buying funds with `fund_type = 'Hedge Fund'`. |
| `discretionary_buyers` | `INTEGER` | Count of distinct buying funds in the discretionary group (`Conglomerate`, `Public Pension Fund`, or `Sovereign Wealth Fund`). |
| `buyer_mix` | `STRING` | `"Hedge-fund-only"` if `discretionary_buyers = 0`; `"Includes discretionary"` otherwise. |
| `funds` | `STRING` | Alphabetically sorted, comma-separated list of the distinct buying funds' names. |
| `total_dollars_added` | `INTEGER` | Sum of dollar value added (`shares_added * Q2_price`) across all qualified buying funds and share classes in USD. |
| `fund_type_breakdown` | `STRING` | Breakdown of distinct qualified buying funds by `Dim_Fund.fund_type` (e.g., `Hedge Fund: 3, Public Pension Fund: 1, Sovereign Wealth Fund: 1`). |

---

## 2. `output/discretionary_signals.csv` (`dashboard/data/discretionary_signals.csv`)

Contains **2026-Q2 Discretionary Smart Money Convergence Signals** restricted to the 3 fundamental/long-horizon institutions (`fund_types = ['Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund']`, i.e., Berkshire Hathaway, CalPERS, and Temasek Holdings, where `2+` of the 3 discretionary funds meet the buyer criteria). Uses the same issuer-level share-class merging (`GOOGL/GOOG` merged into one `ALPHABET INC` row), `is_new_listing = 0` filter, and schema as `convergence_signals.csv`.

| Column | Type | Description |
| :--- | :--- | :--- |
| `cusip` | `STRING` | 9-character CUSIP (or `/`-delimited CUSIPs when multiple share classes of the same issuer are merged, e.g., `02079K305/02079K107`). |
| `ticker` | `STRING` | Exchange ticker symbol (or `/`-delimited tickers when multiple share classes are merged, e.g., `GOOGL/GOOG`). |
| `company_name` | `STRING` | Canonical issuer name. |
| `sector` | `STRING` | Broad sector group mapped from the issuer's SEC EDGAR SIC code (`'Unknown'` fallback). |
| `is_new_listing` | `INTEGER` | `0` for securities held in the prior period (`1` for "New to the sample (no prior-quarter holders)" positions, excluded from main table). |
| `funds_buying` | `INTEGER` | Count of distinct discretionary funds (`>= 2` of 3) meeting the buyer criteria in `2026-Q2` (each fund counted once per issuer). |
| `hedge_fund_buyers` | `INTEGER` | Count of distinct hedge fund buyers (`0` in the discretionary-only subset). |
| `discretionary_buyers` | `INTEGER` | Count of distinct discretionary buying funds (`Conglomerate` + `Public Pension Fund` + `Sovereign Wealth Fund`). |
| `buyer_mix` | `STRING` | Always `"Includes discretionary"` in the discretionary subset. |
| `funds` | `STRING` | Comma-separated list of the distinct discretionary buying funds. |
| `total_dollars_added` | `INTEGER` | Sum of dollar value added (`shares_added * Q2_price`) across the qualified discretionary buyers and share classes in USD. |
| `fund_type_breakdown` | `STRING` | Breakdown of distinct discretionary buying funds by `Dim_Fund.fund_type` (e.g., `Conglomerate: 1, Sovereign Wealth Fund: 1`). |

---

## 3. `output/new_positions_signals.csv` (`dashboard/data/new_positions_signals.csv`)

Contains **2026-Q2 "New to the sample (no prior-quarter holders)"** signals (`is_new_listing = 1`), representing operating common-equity securities that **no fund in the 7-fund sample held in `2026-Q1`** and that were newly established by `3` or more funds in `2026-Q2` (with at least `$1,000,000` added per buying fund).

| Column | Type | Description |
| :--- | :--- | :--- |
| `cusip` | `STRING` | 9-character CUSIP (or `/`-delimited CUSIPs if multiple classes of the same issuer are merged). |
| `ticker` | `STRING` | Exchange ticker symbol. |
| `company_name` | `STRING` | Canonical issuer name. |
| `sector` | `STRING` | Broad sector group mapped from the issuer's SEC EDGAR SIC code (`'Unknown'` fallback). |
| `is_new_listing` | `INTEGER` | Always `1` (indicating zero prior-quarter holders across the 7-fund sample). |
| `funds_buying` | `INTEGER` | Count of distinct funds (`>= 3`) establishing a position of `$1,000,000+` in `2026-Q2`. |
| `funds` | `STRING` | Alphabetically sorted, comma-separated list of the buying funds' names. |
| `total_dollars_added` | `INTEGER` | Sum of Q2 position value added in USD across all qualified buying funds. |
| `fund_type_breakdown` | `STRING` | Breakdown of buying funds by `Dim_Fund.fund_type`. |

---

## 4. `output/top_holdings.csv` (`dashboard/data/top_holdings.csv`)

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

## 5. `output/fund_aum.csv` (`dashboard/data/fund_aum.csv`)

Contains one row per `(period, fund)` in **long format** across all 7 funds and both quarters (`2026-Q1` and `2026-Q2`, 14 rows total), designed for direct Power BI bar/column charts comparing total 13F AUM (`aum_with_options`) against common-equity-only AUM (`aum_equity_only`).

| Column | Type | Description |
| :--- | :--- | :--- |
| `period` | `STRING` | Reporting period (`2026-Q1` or `2026-Q2`). |
| `fund` | `STRING` | Institution name (`Dim_Fund.name`). |
| `fund_type` | `STRING` | Institutional category (`Hedge Fund`, `Conglomerate`, `Public Pension Fund`, or `Sovereign Wealth Fund`). |
| `aum_with_options` | `INTEGER` | Total 13F portfolio market value in USD including `Put`/`Call` options (matches SEC cover-page `<tableValueTotal>`). |
| `aum_equity_only` | `INTEGER` | Total 13F portfolio market value in USD excluding `Put` and `Call` option rows. |

---

## 6. `output/fund_summary.csv` (`dashboard/data/fund_summary.csv`)

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

## 7. `output/sector_by_period.csv` (`dashboard/data/sector_by_period.csv`)

Contains institutional common-equity AUM aggregated by `(period, sector)` in **long format** across `2026-Q1` and `2026-Q2` (excluding `Put`/`Call` option rows and `EXITED` placeholders).

| Column | Type | Description |
| :--- | :--- | :--- |
| `period` | `STRING` | Reporting period (`2026-Q1` or `2026-Q2`). |
| `sector` | `STRING` | Broad sector group mapped from SEC EDGAR SIC codes (`Technology`, `Financials`, `Healthcare`, `Consumer Discretionary`, `Industrials`, `Communication Services`, `Consumer Staples`, `Energy`, `Utilities`, `Materials`, `Real Estate`, or `Unknown`). |
| `value_usd` | `INTEGER` | Total common-equity market value in USD (excluding options) for the sector in the period. |
| `fund_count` | `INTEGER` | Count of distinct funds holding active common equity in the sector during the period. |
