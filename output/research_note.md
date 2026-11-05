# Smart Money Convergence Analysis — Q2 2026 (`2026-Q1` vs `2026-Q2`)

**Author**: Muhammad Kamal  
**Date**: November 5, 2026  
**Data Source**: SEC EDGAR Form 13F-HR & 13F-HR/A Information Tables (`2026-Q1` and `2026-Q2`)

---

## Executive Summary

Across a verified 7-fund institutional sample spanning conglomerates, hedge funds, a public pension fund, and a sovereign wealth fund, total 13F assets under management grew from **`$1,284,805,723,954`** in `2026-Q1` (`$803,285,214,028` excluding options) to **`$1,624,015,283,814`** in `2026-Q2` (`$917,153,241,621` excluding options). Applying a strict share-accumulation convergence filter—requiring a common-equity position to be newly initiated or increased by at least **10% in share count QoQ** with at least **`$1,000,000`** of shares added at Q2 prices—identifies **`63`** full-universe convergence signals (`4+` of `7` funds buying), led by **`KLAC` (`5` funds, `+$2,532,371,809` added)**, **`AMD` (`5` funds, `+$1,195,133,634` added)**, and **`WFC` (`5` funds, `+$903,048,556` added)**. Isolating the 3 long-horizon discretionary institutions (`Berkshire Hathaway`, `CalPERS`, and `Temasek Holdings`) surfaces **`12`** discretionary convergence signals (`2+` of `3` buying)—8 of which do not appear in the full-universe list—headlined by **`GOOGL` (`+$9,618,617,481` added)** and **`GOOG` (`+$9,046,385,016` added)**.

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
- **Redefined Convergence Threshold**: A fund counts as a **buyer** of a security in `2026-Q2` only if:
  1. The holding is common equity (`put_call IS NULL OR put_call = ''`),
  2. The position is `NEW`, **or** its share count increased by at least **10% QoQ** (`(q2_shares - q1_shares) / q1_shares >= 0.10`), and
  3. The dollar value of added shares at Q2 prices (`shares_added * (q2_value_usd / q2_shares)`) is at least **`$1,000,000`**.
- **Sector Classification**: `Dim_Security.security_class` preserves the raw 13F `<titleOfClass>`, while `Dim_Security.sector` maps each issuer's SEC EDGAR SIC code (`data/mappings/sector_cache.json`) to 11 broad sectors (`'Unknown'` fallback).

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

### 2. Sector Coverage Percentage
- Across both periods (`Fact_Holdings WHERE value_usd > 0`), non-`'Unknown'` SIC sectors cover **89.25%** of all common-equity value (`$1,535,399,799,789` of `$1,720,438,455,649`) and **82.07%** of total 13F value including options (`$2,387,138,795,046` of `$2,908,821,007,768`). The remaining **10.75%** of equity value consists primarily of broad index ETFs (`IVV`, `VOO`, `SPY`, `QQQ`, `IWM`) that are structured as investment trusts rather than SIC-classified operating corporations.
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

### 3. Full-Universe vs. Discretionary Convergence Signals (`2026-Q2`)
- **Full Universe (`min_funds = 4`)**: **`63`** securities met the buyer criteria across `4+` funds (`6` securities with `5` buying funds and `57` with `4` buying funds). Because 4 of the 7 funds in our sample are high-breadth hedge funds (`Citadel Advisors`, `Two Sigma Investments`, `Renaissance Technologies`, and `Bridgewater Associates`), **`30` of the `63`** full-universe signals are pure `Hedge Fund: 4` signals.
- **Discretionary Subset (`Conglomerate`, `Public Pension Fund`, `Sovereign Wealth Fund`, `2+` of `3` buying)**: **`12`** securities met the buyer criteria. Only **`4`** overlap with the 63-stock full-universe signal list (`KLAC`, `BKNG`, `WMT`, `AMD`), whereas **`8`** are unique to the discretionary signal list (`GOOGL`, `GOOG`, `C`, `GLW`, `NTRA`, `ATAT`, `COHR`, `UEC`). Most notably, `Berkshire Hathaway` and `Temasek Holdings` both accumulated **`GOOGL` (`+$9,618,617,481` added)** and **`GOOG` (`+$9,046,385,016` added)** in `2026-Q2`, which missed the `4+` full-universe threshold because quantitative hedge funds trimmed or increased by `<10%` in shares.
- **Source Query** (`sql/queries.sql` — Query 1 & `src/analysis.py::get_convergence_signals`):
  ```sql
  -- Full Universe: Query 1 in sql/queries.sql (HAVING COUNT(DISTINCT qb.fund_id) >= 4)
  -- Discretionary Subset: Query 1 filtered with AND f.fund_type IN ('Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund') HAVING COUNT(DISTINCT qb.fund_id) >= 2
  ```

### 4. Sector Rotation (`2026-Q1` vs `2026-Q2`)
- **`Technology`** recorded the largest common-equity dollar inflow across the 7 funds, growing **`+$52,933,434,499` (+23.10%)** from `$229,100,599,115` (`28.52%` of Q1 equity AUM) to `$282,034,033,614` (`30.75%` of Q2 equity AUM).
- **`Financials`** gained **`+$14,249,245,818` (+9.25%)** from `$153,967,632,776` to `$168,216,878,594`, **`Industrials`** gained **`+$9,496,463,375` (+13.66%)**, and **`Healthcare`** gained **`+$8,895,997,077` (+16.64%)**.
- **`Energy`** was the only sector with a net common-equity contraction, declining **`-$5,808,834,193` (-11.18%)** from `$51,962,745,245` (`6.47%` of Q1 equity AUM) to `$46,153,911,052` (`5.03%` of Q2 equity AUM).
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

## Top 15 Convergence Signal Stocks — Q2 2026 (Full Universe, `min_funds = 4`)

*Source Query*: `sql/queries.sql` — Query 1 (`get_convergence_signals('2026-Q2', min_funds=4)`)

| Rank | Ticker | Company Name | Sector | Funds Buying | Buying Funds | Total Dollars Added (USD) | Fund Type Breakdown |
| :---: | :--- | :--- | :--- | :---: | :--- | ---: | :--- |
| 1 | `KLAC` | KLA CORP | Technology | 5 | Bridgewater Associates, CalPERS, Citadel Advisors, Temasek Holdings, Two Sigma Investments | `$2,532,371,809` | Hedge Fund: 3, Public Pension Fund: 1, Sovereign Wealth Fund: 1 |
| 2 | `AMD` | ADVANCED MICRO DEVICES INC | Technology | 5 | CalPERS, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$1,195,133,634` | Hedge Fund: 3, Public Pension Fund: 1, Sovereign Wealth Fund: 1 |
| 3 | `WFC` | WELLS FARGO & CO | Financials | 5 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$903,048,556` | Hedge Fund: 4, Sovereign Wealth Fund: 1 |
| 4 | `BKNG` | BOOKING HOLDINGS INC | Industrials | 5 | Bridgewater Associates, CalPERS, Citadel Advisors, Temasek Holdings, Two Sigma Investments | `$705,311,721` | Hedge Fund: 3, Public Pension Fund: 1, Sovereign Wealth Fund: 1 |
| 5 | `CBRE` | CBRE GROUP INC | Real Estate | 5 | Bridgewater Associates, CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$268,148,933` | Hedge Fund: 4, Public Pension Fund: 1 |
| 6 | `FORM` | FORMFACTOR INC | Technology | 5 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$119,590,856` | Hedge Fund: 4, Sovereign Wealth Fund: 1 |
| 7 | `IVV` | ISHARES TR | Unknown | 4 | Bridgewater Associates, CalPERS, Citadel Advisors, Renaissance Technologies | `$20,871,368,839` | Hedge Fund: 3, Public Pension Fund: 1 |
| 8 | `SPCX` | SPACE EXPLORATION TECHNOLOGIES CORP | Technology | 4 | Bridgewater Associates, Citadel Advisors, Temasek Holdings, Two Sigma Investments | `$2,861,656,740` | Hedge Fund: 3, Sovereign Wealth Fund: 1 |
| 9 | `STX` | SEAGATE TECHNOLOGY HLDNGS PL | Technology | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$1,333,294,180` | Hedge Fund: 3, Public Pension Fund: 1 |
| 10 | `NFLX` | NETFLIX INC. | Communication Services | 4 | Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$1,058,109,711` | Hedge Fund: 3, Sovereign Wealth Fund: 1 |
| 11 | `MDT` | MEDTRONIC PLC | Healthcare | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$815,269,329` | Hedge Fund: 4 |
| 12 | `BLK` | BLACKROCK INC | Financials | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$778,654,630` | Hedge Fund: 4 |
| 13 | `WMT` | WALMART INC | Consumer Staples | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Temasek Holdings | `$755,714,705` | Hedge Fund: 2, Public Pension Fund: 1, Sovereign Wealth Fund: 1 |
| 14 | `ICE` | INTERCONTINENTAL EXCHANGE IN | Financials | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$572,770,629` | Hedge Fund: 4 |
| 15 | `SPGI` | S&P GLOBAL INC | Financials | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$562,871,603` | Hedge Fund: 4 |

---

## Discretionary Convergence Signals — Q2 2026 (`Conglomerate`, `Public Pension Fund`, `Sovereign Wealth Fund`)

*Source Query*: `get_convergence_signals('2026-Q2', fund_types=['Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund'])`

| Rank | Ticker | Company Name | Sector | Funds Buying | Buying Funds | Total Dollars Added (USD) | In Full 4+ List? |
| :---: | :--- | :--- | :--- | :---: | :--- | ---: | :---: |
| 1 | `GOOGL` | ALPHABET INC-CL A | Technology | 2 | Berkshire Hathaway, Temasek Holdings | `$9,618,617,481` | No (`3` buyers overall) |
| 2 | `GOOG` | ALPHABET INC-CL C | Technology | 2 | Berkshire Hathaway, Temasek Holdings | `$9,046,385,016` | No (`3` buyers overall) |
| 3 | `KLAC` | KLA CORP | Technology | 2 | CalPERS, Temasek Holdings | `$1,686,087,931` | Yes (`5` buyers overall) |
| 4 | `BKNG` | BOOKING HOLDINGS INC | Industrials | 2 | CalPERS, Temasek Holdings | `$578,415,180` | Yes (`5` buyers overall) |
| 5 | `C` | CITIGROUP INC | Financials | 2 | CalPERS, Temasek Holdings | `$226,493,349` | No (`2` buyers overall) |
| 6 | `WMT` | WALMART INC | Consumer Staples | 2 | CalPERS, Temasek Holdings | `$224,060,786` | Yes (`4` buyers overall) |
| 7 | `AMD` | ADVANCED MICRO DEVICES INC | Technology | 2 | CalPERS, Temasek Holdings | `$204,656,336` | Yes (`5` buyers overall) |
| 8 | `GLW` | CORNING INC | Materials | 2 | CalPERS, Temasek Holdings | `$89,434,217` | No (`3` buyers overall) |
| 9 | `NTRA` | NATERA INC | Healthcare | 2 | CalPERS, Temasek Holdings | `$53,204,471` | No (`3` buyers overall) |
| 10 | `ATAT` | ATOUR LIFESTYLE HLDGS LTD | Consumer Discretionary | 2 | CalPERS, Temasek Holdings | `$40,828,370` | No (`3` buyers overall) |
| 11 | `COHR` | COHERENT CORP | Technology | 2 | CalPERS, Temasek Holdings | `$40,785,831` | No (`2` buyers overall) |
| 12 | `UEC` | URANIUM ENERGY CORP | Materials | 2 | CalPERS, Temasek Holdings | `$5,946,553` | No (`3` buyers overall) |

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

## Risk Considerations

- **45-Day Reporting Lag**: Form 13F filings are submitted up to 45 days after quarter-end; high-turnover quantitative managers may have already rotated out of positions disclosed at quarter-end.
- **Asymmetric Long-Only Disclosure**: Form 13F captures long US-listed equities and exchange-traded options (`Put`/`Call`) but omits short equity sales, OTC derivatives, and non-US local listings.
- **Quantitative Breadth vs. Discretionary Conviction**: Multi-manager and quantitative hedge funds hold thousands of names (`13,572` active rows at Citadel Advisors; `5,017` at Two Sigma Investments), making it essential to cross-reference full-universe signals against the discretionary subset (`output/discretionary_signals.csv`).

---

## Conclusion

Combining a share-based accumulation threshold (`>= 10%` QoQ share increase or `NEW` entry, `>= $1,000,000` added value, excluding options) with a discretionary vs. full-universe segmentation separates broad quantitative factor rebalancing from high-conviction fundamental accumulation. In `2026-Q2`, the strongest cross-archetype convergence occurred in semiconductor and AI infrastructure leaders (`KLAC` `+$2.53B` across 5 funds; `AMD` `+$1.20B` across 5 funds; `SPCX` `+$2.86B` across 4 funds) alongside massive discretionary accumulation in `GOOGL` (`+$9.62B`) and `GOOG` (`+$9.05B`) by `Berkshire Hathaway` and `Temasek Holdings`.
