# Smart Money Convergence Analysis — Q2 2026 (`2026-Q1` vs `2026-Q2`)

**Author**: Muhammad Kamal  
**Date**: November 5, 2026  
**Data Source**: SEC EDGAR Form 13F-HR & 13F-HR/A Information Tables (`2026-Q1` and `2026-Q2`)

---

## Executive Summary

Across a verified 7-fund institutional sample spanning conglomerates, hedge funds, a public pension fund, and a sovereign wealth fund, total 13F assets under management grew from **`$1,284,805,723,954`** in `2026-Q1` (`$803,285,214,028` excluding options) to **`$1,624,015,283,814`** in `2026-Q2` (`$917,153,241,621` excluding options). Applying a strict **split-adjusted** share-accumulation convergence filter—requiring an operating common-equity position (excluding options, ETFs, and index trusts) to be newly initiated or increased by at least **10% in split-adjusted share count QoQ** with at least **`$1,000,000`** of shares added at Q2 prices—identifies **`59`** full-universe convergence signals (`4+` of `7` funds buying), led by **`AMD` (`5` funds, `+$1,195,133,634` added)**, **`WFC` (`5` funds, `+$903,048,556` added)**, **`CBRE` (`5` funds, `+$268,148,933` added)**, **`FORM` (`5` funds, `+$119,590,856` added)**, and **`SPCX` (`4` funds, `+$2,861,656,740` added)**. Isolating the 3 long-horizon discretionary institutions (`Berkshire Hathaway`, `CalPERS`, and `Temasek Holdings`) surfaces **`10`** discretionary convergence signals (`2+` of `3` buying)—8 of which do not appear in the full-universe list—headlined by **`GOOGL` (`+$9,618,617,481` added)** and **`GOOG` (`+$9,046,385,016` added)**.

---

## Data & Methodology

Institutional investment managers exercising discretion over `$100M+` in Section 13(f) securities file Form 13F within 45 days of each quarter-end. This study analyzes 14 authoritative SEC EDGAR filings (`2026-Q1` and `2026-Q2`) across 7 institutions representing four distinct institutional archetypes:

| Fund Name | CIK | Fund Type | Q1 2026 Accession | Q2 2026 Accession |
| :--- | :--- | :--- | :--- | :--- |
| **Berkshire Hathaway** | `0001067983` | Conglomerate | `0001193125-26-226661` | `0001193125-26-352200` |
| **Citadel Advisors** | `0001423053` | Hedge Fund | `0001104659-26-062477` | `0001104659-26-104387` *(13F-HR/A restatement)* |
| **CalPERS** | `0000919079` | Public Pension Fund | `0000919079-26-000006` | `0000919079-26-000011` |
| **Two Sigma Investments** | `0001179392` | Hedge Fund | `0000899140-26-000547` | `0000899140-26-000855` |
| **Renaissance Technologies** | `0001037389` | Hedge Fund | `0001037389-26-000033` | `0001037389-26-000059` |
| **Temasek Holdings** | `0001021944` | Sovereign Wealth Fund | `0001021944-26-000011` | `0001021944-26-000013` |
| **Bridgewater Associates** | `0001350694` | Hedge Fund | `0001350694-26-000002` | `0001350694-26-000003` |

- **Cover-Page Reconciliation & Multi-Manager Aggregation**: All 14 filings (`52,269` raw XML `<infoTable>` rows) are aggregated by `(fund_cik, period, cusip, put_call)` into `46,865` active holding rows (`plus 3,446 EXITED tracking rows = 50,311 rows in Fact_Holdings`), reconciling with `$0` variance against each filing's cover-page `<tableValueTotal>`.
- **Stock Split Detection & Adjustment (`src/database.py::detect_splits`)**: Corporate stock splits between `2026-Q1` and `2026-Q2` (`KLAC` 10-for-1 on June 11, 2026; `BKNG` 25-for-1 on April 2, 2026; `CVNA` 5-for-1) inflate post-split Q2 share counts relative to pre-split Q1 share counts. The pipeline computes median implied price (`value_usd / shares`) per CUSIP across funds in each period, combines ground-truth `SPLIT_OVERRIDES` in `config.py` with automated detection across common split factors `(2, 3, 4, 5, 8, 10, 15, 20, 25, 30)`, and multiplies `2026-Q1` common-equity shares by the split factor before computing `qoq_change_flag` and QoQ share changes.
- **Redefined Convergence Threshold & ETF Separation**: A fund counts as a **buyer** of a security in `2026-Q2` only if:
  1. The holding is operating common equity (`put_call IS NULL OR put_call = ''`, excluding ETFs and index trusts such as `IVV`, `SPY`, `VOO`, `QQQ`, which are reported separately via `get_etf_convergence_signals`),
  2. The position is `NEW`, **or** its split-adjusted share count increased by at least **10% QoQ** (`(q2_shares - q1_split_adj_shares) / q1_split_adj_shares >= 0.10`), and
  3. The dollar value of added shares at Q2 prices (`shares_added * (q2_value_usd / q2_shares)`) is at least **`$1,000,000`**.
- **Sector Classification**: `Dim_Security.security_class` preserves the raw 13F `<titleOfClass>`, while `Dim_Security.sector` maps each issuer's SEC EDGAR SIC code (`data/mappings/sector_cache.json`) and curated overrides (`BKNG` -> `Consumer Discretionary`, `KMB` -> `Consumer Staples`, `ACN`/`IT` -> `Technology`, `V`/`MA` -> `Financials`) to 11 broad sectors (`'Unknown'` fallback).

---

## Key Findings (Every Claim Backed by SQL Query Output)

### 1. Total Institutional AUM With and Without Options
- In `2026-Q1`, total 13F AUM across the 7 funds was **`$1,284,805,723,954`** including options and **`$803,285,214,028`** excluding options (`$481,520,509,926` or **37.48%** in `Put`/`Call` options).
- In `2026-Q2`, total 13F AUM rose **+26.40%** to **`$1,624,015,283,814`** including options and **+14.18%** to **`$917,153,241,621`** excluding options (`$706,862,042,193` or **43.53%** in options, driven primarily by Citadel Advisors' `$700,875,428,616` option book across `7,221` option positions).
- **Source Query** (`src/analysis.py::get_aum_by_period`):
  ```sql
  SELECT
      h.period,
      COUNT(DISTINCT h.fund_id) AS fund_count,
      SUM(CASE WHEN h.value_usd > 0 THEN h.value_usd ELSE 0 END) AS aum_with_options_usd,
      SUM(CASE WHEN h.value_usd > 0 AND (h.put_call IS NULL OR h.put_call = '') THEN h.value_usd ELSE 0 END) AS aum_without_options_usd,
      SUM(CASE WHEN h.value_usd > 0 AND h.put_call IN ('Put', 'Call') THEN h.value_usd ELSE 0 END) AS options_aum_usd,
      ROUND(
          SUM(CASE WHEN h.value_usd > 0 AND h.put_call IN ('Put', 'Call') THEN h.value_usd ELSE 0 END) * 100.0
          / SUM(CASE WHEN h.value_usd > 0 THEN h.value_usd ELSE 0 END), 2
      ) AS options_pct_of_total
  FROM Fact_Holdings h
  GROUP BY h.period
  ORDER BY h.period;
  ```

### 2. Impact of Stock Split Adjustments (`KLAC`, `BKNG`, `CVNA`)
- Across the dataset, `detect_splits` identified **10** stock splits (`2` ground-truth overrides and `8` auto-detected splits: `5` forward and `3` reverse), adjusting `41` prior-period (`2026-Q1`) holding rows:
  - **`KLAC` (`482480100`, 10-for-1 split on June 11, 2026)**: Without split adjustment, 5 funds appeared to increase shares by `>200%`. After multiplying Q1 shares by `10`, `Temasek Holdings` held **`323,870`** split-adjusted Q1 shares (`32,387` raw) vs. **`323,870`** Q2 shares (**0.00% change, `UNCHANGED`**), `CalPERS` trimmed **-0.92%** (`5,946,370` -> `5,891,593`), and `Bridgewater Associates` cut **-69.81%** (`1,086,740` -> `328,070`). Only **2** funds (`Citadel Advisors` `+570.77%` and `Two Sigma Investments` `+106.12%`) actually bought `KLAC`.
  - **`BKNG` (`09857L108`, 25-for-1 split on April 2, 2026)**: After multiplying Q1 shares by `25`, `CalPERS` reduced its stake by **-17.91%** (`2,037,225` -> `1,672,345`), `Citadel Advisors` reduced by **-72.00%** (`2,253,375` -> `631,052`), and `Two Sigma Investments` added only **+1.36%** (`132,500` -> `134,300`, below the `10%` threshold). Only **2** funds (`Bridgewater Associates` and `Temasek Holdings`) qualified as buyers.
  - **`CVNA` (`146869102`, auto-detected 5-for-1 split)**: After multiplying Q1 shares by `5`, `CalPERS` (`+4.87%`) and `Renaissance Technologies` (`-14.71%`) no longer qualified as buyers, leaving only **2** buying funds.
- **Source Query** (`tests/test_parse_holdings.py::test_temasek_klac_split_adjusted_change_is_zero`):
  ```sql
  SELECT f.name, h.period, h.shares, h.qoq_change_flag
  FROM Fact_Holdings h
  JOIN Dim_Fund f ON h.fund_id = f.fund_id
  JOIN Dim_Security s ON h.security_id = s.security_id
  WHERE s.cusip IN ('482480100', '09857L108') AND (h.put_call IS NULL OR h.put_call = '')
  ORDER BY s.cusip, f.name, h.period;
  ```

### 3. Sector Coverage Percentage
- Across both periods (`Fact_Holdings WHERE value_usd > 0`), non-`'Unknown'` sectors cover **89.42%** of all common-equity value and **82.25%** of total 13F value including options. The remaining **10.58%** of equity value consists primarily of broad index ETFs (`IVV`, `VOO`, `SPY`, `QQQ`, `IWM`) that are structured as investment trusts rather than single-sector operating corporations.
- **Source Query**:
  ```sql
  SELECT
      ROUND(SUM(CASE WHEN s.sector != 'Unknown' THEN h.value_usd ELSE 0 END) * 100.0 / SUM(h.value_usd), 2) AS all_cov_pct,
      ROUND(
          SUM(CASE WHEN s.sector != 'Unknown' AND (h.put_call IS NULL OR h.put_call = '') THEN h.value_usd ELSE 0 END) * 100.0
          / SUM(CASE WHEN h.put_call IS NULL OR h.put_call = '' THEN h.value_usd ELSE 0 END), 2
      ) AS eq_cov_pct
  FROM Fact_Holdings h
  JOIN Dim_Security s ON h.security_id = s.security_id
  WHERE h.value_usd > 0;
  ```

### 4. Full-Universe vs. Discretionary Convergence Signals (`2026-Q2`)
- **Full Universe (`min_funds = 4`, operating equities only)**: **`59`** operating-equity securities met the split-adjusted buyer criteria across `4+` funds (`4` securities with `5` buying funds and `55` with `4` buying funds). Because 4 of the 7 funds in our sample are high-breadth hedge funds (`Citadel Advisors`, `Two Sigma Investments`, `Renaissance Technologies`, and `Bridgewater Associates`), **`31` of the `59`** full-universe signals are pure `Hedge Fund: 4` signals.
- **Discretionary Subset (`Conglomerate`, `Public Pension Fund`, `Sovereign Wealth Fund`, `2+` of `3` buying)**: **`10`** securities met the split-adjusted buyer criteria. Only **`2`** overlap with the 59-stock full-universe signal list (`AMD`, `WMT`), whereas **`8`** are unique to the discretionary signal list (`GOOGL`, `GOOG`, `C`, `GLW`, `NTRA`, `ATAT`, `COHR`, `UEC`). Most notably, `Berkshire Hathaway` and `Temasek Holdings` both accumulated **`GOOGL` (`+$9,618,617,481` added)** and **`GOOG` (`+$9,046,385,016` added)** in `2026-Q2`, which missed the `4+` full-universe threshold because only 3 funds in total met the `>=10%` share-increase threshold.
- **Source Query** (`sql/queries.sql` — Query 1 & `src/analysis.py::get_convergence_signals`):
  ```sql
  -- Full Universe: Query 1 in sql/queries.sql (HAVING COUNT(DISTINCT qb.fund_id) >= 4)
  -- Discretionary Subset: Query 1 filtered with AND f.fund_type IN ('Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund') HAVING COUNT(DISTINCT qb.fund_id) >= 2
  ```

### 5. Sector Rotation (`2026-Q1` vs `2026-Q2`)
- **`Technology`** recorded the largest common-equity dollar inflow across the 7 funds, growing **`+$53,218,012,069` (+23.13%)** from `$230,064,460,040` in `2026-Q1` to `$283,282,472,109` in `2026-Q2`.
- **`Financials`** gained **`+$14,679,664,217` (+9.05%)** from `$162,164,172,175` to `$176,843,836,392`, **`Healthcare`** gained **`+$8,895,997,077` (+16.64%)**, **`Industrials`** gained **`+$8,642,889,659` (+15.36%)**, and **`Consumer Discretionary`** gained **`+$5,243,489,654` (+10.89%)**.
- **`Energy`** was the only sector with a net common-equity contraction, declining **`-$5,808,834,193` (-11.18%)** from `$51,962,745,245` to `$46,153,911,052`.
- **Source Query** (`sql/queries.sql` — Query 6):
  ```sql
  SELECT s.sector,
         SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END) AS q1_equity_aum_usd,
         SUM(CASE WHEN h.period = '2026-Q2' THEN h.value_usd ELSE 0 END) AS q2_equity_aum_usd,
         (SUM(CASE WHEN h.period = '2026-Q2' THEN h.value_usd ELSE 0 END) -
          SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END)) AS qoq_dollar_change_usd,
         ROUND((SUM(CASE WHEN h.period = '2026-Q2' THEN h.value_usd ELSE 0 END) -
                SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END)) * 100.0
               / NULLIF(SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END), 0), 2) AS qoq_pct_change
  FROM Fact_Holdings h JOIN Dim_Security s ON h.security_id = s.security_id
  WHERE h.period IN ('2026-Q1', '2026-Q2') AND (h.put_call IS NULL OR h.put_call = '') AND h.value_usd > 0
  GROUP BY s.sector ORDER BY qoq_dollar_change_usd DESC;
  ```

---

## Top 15 Convergence Signal Stocks — Q2 2026 (Full Universe, Operating Equities Only, `min_funds = 4`)

*Source Query*: `sql/queries.sql` — Query 1 (`get_convergence_signals('2026-Q2', min_funds=4)`)

| Rank | Ticker | Company Name | Sector | Funds Buying | Buying Funds | Total Dollars Added (USD) | Fund Type Breakdown |
| :---: | :--- | :--- | :--- | :---: | :--- | ---: | :--- |
| 1 | `AMD` | ADVANCED MICRO DEVICES INC | Technology | 5 | CalPERS, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$1,195,133,634` | Hedge Fund: 3, Public Pension Fund: 1, Sovereign Wealth Fund: 1 |
| 2 | `WFC` | WELLS FARGO & CO | Financials | 5 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$903,048,556` | Hedge Fund: 4, Sovereign Wealth Fund: 1 |
| 3 | `CBRE` | CBRE GROUP INC | Real Estate | 5 | Bridgewater Associates, CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$268,148,933` | Hedge Fund: 4, Public Pension Fund: 1 |
| 4 | `FORM` | FORMFACTOR INC | Technology | 5 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$119,590,856` | Hedge Fund: 4, Sovereign Wealth Fund: 1 |
| 5 | `SPCX` | SPACE EXPLORATION TECHNOLOGIES CORP | Technology | 4 | Bridgewater Associates, Citadel Advisors, Temasek Holdings, Two Sigma Investments | `$2,861,656,740` | Hedge Fund: 3, Sovereign Wealth Fund: 1 |
| 6 | `STX` | SEAGATE TECHNOLOGY HLDNGS PL | Technology | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$1,333,294,180` | Hedge Fund: 3, Public Pension Fund: 1 |
| 7 | `NFLX` | NETFLIX INC. | Communication Services | 4 | Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$1,058,109,711` | Hedge Fund: 3, Sovereign Wealth Fund: 1 |
| 8 | `MDT` | MEDTRONIC PLC | Healthcare | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$815,269,329` | Hedge Fund: 4 |
| 9 | `BLK` | BLACKROCK INC | Financials | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$778,654,630` | Hedge Fund: 4 |
| 10 | `WMT` | WALMART INC | Consumer Staples | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Temasek Holdings | `$755,714,705` | Hedge Fund: 2, Public Pension Fund: 1, Sovereign Wealth Fund: 1 |
| 11 | `ICE` | INTERCONTINENTAL EXCHANGE IN | Financials | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$572,770,629` | Hedge Fund: 4 |
| 12 | `SPGI` | S&P GLOBAL INC | Financials | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$562,871,603` | Hedge Fund: 4 |
| 13 | `CMG` | CHIPOTLE MEXICAN GRILL INC | Consumer Discretionary | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$558,661,072` | Hedge Fund: 3, Public Pension Fund: 1 |
| 14 | `MPWR` | MONOLITHIC PWR SYS INC | Technology | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$491,800,836` | Hedge Fund: 3, Public Pension Fund: 1 |
| 15 | `DOW` | DOW HLDGS INC | Materials | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$491,407,926` | Hedge Fund: 3, Public Pension Fund: 1 |

---

## Discretionary Convergence Signals — Q2 2026 (`Conglomerate`, `Public Pension Fund`, `Sovereign Wealth Fund`)

*Source Query*: `get_convergence_signals('2026-Q2', fund_types=['Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund'])`

| Rank | Ticker | Company Name | Sector | Funds Buying | Buying Funds | Total Dollars Added (USD) | In Full 4+ List? |
| :---: | :--- | :--- | :--- | :---: | :--- | ---: | :---: |
| 1 | `GOOGL` | ALPHABET INC-CL A | Technology | 2 | Berkshire Hathaway, Temasek Holdings | `$9,618,617,481` | No (`3` buyers overall) |
| 2 | `GOOG` | ALPHABET INC-CL C | Technology | 2 | Berkshire Hathaway, Temasek Holdings | `$9,046,385,016` | No (`3` buyers overall) |
| 3 | `C` | CITIGROUP INC | Financials | 2 | CalPERS, Temasek Holdings | `$226,493,349` | No (`3` buyers overall) |
| 4 | `WMT` | WALMART INC | Consumer Staples | 2 | CalPERS, Temasek Holdings | `$224,060,786` | Yes (`4` buyers overall) |
| 5 | `AMD` | ADVANCED MICRO DEVICES INC | Technology | 2 | CalPERS, Temasek Holdings | `$204,656,336` | Yes (`5` buyers overall) |
| 6 | `GLW` | CORNING INC | Materials | 2 | CalPERS, Temasek Holdings | `$89,434,217` | No (`2` buyers overall) |
| 7 | `NTRA` | NATERA INC | Healthcare | 2 | CalPERS, Temasek Holdings | `$53,204,471` | No (`3` buyers overall) |
| 8 | `ATAT` | ATOUR LIFESTYLE HLDGS LTD | Consumer Discretionary | 2 | CalPERS, Temasek Holdings | `$40,828,370` | No (`3` buyers overall) |
| 9 | `COHR` | COHERENT CORP | Technology | 2 | CalPERS, Temasek Holdings | `$40,785,831` | No (`3` buyers overall) |
| 10 | `UEC` | URANIUM ENERGY CORP | Materials | 2 | CalPERS, Temasek Holdings | `$5,946,553` | No (`2` buyers overall) |

---

## Separate ETF & Index Trust Convergence Table — Q2 2026 (`min_funds = 3`)

*Source Query*: `src/analysis.py::get_etf_convergence_signals('2026-Q2', min_funds=3)`

| Rank |CUSIP | Ticker | ETF / Trust Name | Security Class | Funds Buying | Buying Funds | Total Dollars Added (USD) |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- | ---: |
| 1 | `464287200` | `IVV` | ISHARES CORE S&P 500 ETF | `CORE S&P500 ETF` | 4 | Bridgewater Associates, CalPERS, Citadel Advisors, Renaissance Technologies | `$20,871,368,839` |
| 2 | `78462F103` | `SPY` | STATE STR SPDR S&P 500 ETF T | `TR UNIT` | 3 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies | `$943,619,319` |
| 3 | `81369Y506` | `XLE` | ENERGY SELECT SECTOR SPDR FUND | `ST STR ENERG ETF` | 3 | Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$418,516,572` |
| 4 | `922908363` | `VOO` | VANGUARD S&P 500 ETF | `S&P 500 ETF SHS` | 3 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies | `$298,268,533` |
| 5 | `92189F106` | `GDX` | VANECK GOLD MINERS ETF | `GOLD MINERS ETF` | 3 | Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$275,551,700` |
| 6 | `81369Y209` | `XLV` | HEALTH CARE SELECT SECTOR SPDR FUND | `STATE STREET HEA` | 3 | Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$232,991,575` |
| 7 | `46138E628` | `KBE` | INVESCO KBW BANK ETF | `KBW BK ETF` | 3 | Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$85,944,575` |
| 8 | `78464A755` | `XME` | SPDR S&P METALS & MINING ETF | `STATE STREET SPD` | 3 | Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$73,985,295` |
| 9 | `464287432` | `TLT` | ISHARES 20+ YEAR TREASURY BOND ETF | `20 YR TR BD ETF` | 3 | Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$61,225,113` |
| 10 | `78463V107` | `GLD` | SPDR GOLD TRUST | `GOLD SHS` | 3 | Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$39,761,464` |

---

## Notable New & Exited Positions (`2026-Q2`)

- **Largest Newly Initiated Positions (`4,605` total `NEW` rows in `2026-Q2`)**:
  - **Space Exploration Technologies Corp (`SPCX`, CUSIP `84615Q103`)**: Four funds initiated common-equity stakes in `2026-Q2` totaling **`$2,861,656,740`** (`Temasek Holdings` `9,831,945` shares / `$1,679,886,123`; `Citadel Advisors` `5,129,884` shares / `$876,491,980`; `Two Sigma Investments` `1,775,121` shares / `$303,297,174`; and `Bridgewater Associates` `11,597` shares / `$1,981,463`). In addition, `Citadel Advisors` initiated `$1,415,045,434` in `SPCX` Call options and `$973,491,936` in `SPCX` Put options.
  - **Alphabet Class C (`GOOG`, CUSIP `02079K107`)**: `Temasek Holdings` initiated a new `2,000,000`-share stake worth **`$706,660,000`** (`1.90%` of its portfolio), alongside `Berkshire Hathaway`'s `23,619,600`-share increase (`+$8,345,519,705` added).
  - **CrowdStrike (`CRWD`, CUSIP `22788C105`)** & **Intuit (`INTU`, CUSIP `461202103`)**: `Renaissance Technologies` initiated `748,960` shares of `CRWD` worth **`$571,561,334`**, while `Two Sigma Investments` initiated `2,161,507` shares of `INTU` worth **`$564,153,327`**.
  - *Source Query*: `sql/queries.sql` — Query 2 (`get_qoq_new_positions('2026-Q2')`).
- **Largest Exited Positions (`3,446` total `EXITED` rows in `2026-Q2`)**:
  - **Western Digital note (`WDC`, CUSIP `958102AT2`)**: `Citadel Advisors` exited a `2026-Q1` position valued at **`$696,712,587`**.
  - **Honeywell International (`HON`, CUSIP `438516106`)**: Both `Two Sigma Investments` (`1,737,296` Q1 shares worth **`$392,681,015`**) and `CalPERS` (`1,105,154` Q1 shares worth **`$249,797,959`**) completely exited their common-equity positions in `2026-Q2`.
  - **AppLovin Corp (`APP`, CUSIP `03831W108`)**: `Renaissance Technologies` exited its `436,540`-share Q1 stake worth **`$173,742,920`**.
  - *Source Query*: `sql/queries.sql` — Query 3 (`get_qoq_exited_positions('2026-Q2')`).

---

## Limitations

1. **Long-Only Disclosure**: Form 13F only captures long US-listed Section 13(f) equities and exchange-traded options (`Put`/`Call`). It omits short equity sales, total-return swaps, OTC derivatives, and non-US local listings—meaning a reported long equity stake may hedge an unreported short position.
2. **45-Day Reporting Delay**: Form 13F filings are submitted up to 45 calendar days after quarter-end; high-turnover managers may have already rotated out of positions disclosed at quarter-end.
3. **Quantitative & Market-Making Noise**: Share increases at quantitative and multi-manager hedge funds (`Citadel Advisors`, `Two Sigma Investments`, `Renaissance Technologies`) frequently reflect market-making inventory, options delta-hedging, or statistical arbitrage factor turnover rather than fundamental directional conviction. Cross-referencing full-universe signals against the discretionary subset (`output/discretionary_signals.csv`) is therefore essential.

---

## Conclusion

Adjusting prior-quarter share counts for stock splits (`KLAC` 10-for-1, `BKNG` 25-for-1, `CVNA` 5-for-1) and separating ETFs/index trusts (`IVV`, `SPY`, `VOO`) eliminates structural false positives from the convergence signal. In `2026-Q2`, the strongest split-adjusted operating-equity accumulation occurred in **`AMD` (`5` funds, `+$1.20B` added)**, **`WFC` (`5` funds, `+$903.05M` added)**, **`CBRE` (`5` funds, `+$268.15M` added)**, **`FORM` (`5` funds, `+$119.59M` added)**, and **`SPCX` (`4` funds, `+$2.86B` added)**, alongside high-conviction discretionary accumulation in **`GOOGL` (`+$9.62B`)** and **`GOOG` (`+$9.05B`)** by `Berkshire Hathaway` and `Temasek Holdings`.
