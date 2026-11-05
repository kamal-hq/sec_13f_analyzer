# Smart Money Convergence Analysis — Q2 2026 (`2026-Q1` vs `2026-Q2`)

**Author**: Muhammad Kamal  
**Date**: November 5, 2026  
**Data Source**: SEC EDGAR Form 13F-HR & 13F-HR/A Information Tables (`2026-Q1` and `2026-Q2`)

---

## Executive Summary

**Lead Finding — Broad Convergence Is Dominated by Quantitative Funds; Discretionary Convergence (`3`-Fund Sample) Is More Informative**:  
Across our 7-fund institutional sample, 4 of the 7 managers are high-breadth quantitative or multi-manager hedge funds (`Citadel Advisors`, `Two Sigma Investments`, `Renaissance Technologies`, and `Bridgewater Associates`). Consequently, broad full-universe convergence (`min_funds = 4`, seasoned operating equities) is heavily dominated by quantitative turnover: **`31` of the `56` full-universe convergence signals (`55.4%`) are pure `Hedge Fund: 4` signals** with zero participation from long-horizon discretionary managers, and **all `56` signals require at least 2 hedge funds**. Isolating the discretionary subset (`Conglomerate`, `Public Pension Fund`, and `Sovereign Wealth Fund`—while explicitly noting that **our discretionary sample comprises only `3` funds**: `Berkshire Hathaway`, `CalPERS`, and `Temasek Holdings`) produces a cleaner, higher-conviction fundamental signal (`9` issuer-level signals with `2+` of `3` buying, `7` of which do not appear in the 56-stock full list), headlined by merged **`GOOGL/GOOG` (`ALPHABET INC`, `+$18,665,002,497` added across Class A and Class C by `Berkshire Hathaway` and `Temasek Holdings`)** and **`C` (`CITIGROUP INC`, `+$226,493,349` added by `CalPERS` and `Temasek Holdings`)**.

Across all 7 institutions, total 13F assets under management grew from **`$1,284,805,723,954`** in `2026-Q1` (`$803,285,214,028` excluding options) to **`$1,624,015,283,814`** in `2026-Q2` (`$917,153,241,621` excluding options). Applying our refined convergence methodology—merging multiple share classes at the 6-character CUSIP issuer level, adjusting prior-quarter shares only for **`yfinance`-confirmed stock splits** (`BKNG` 25-for-1, `KLAC` 10-for-1, `CVNA` 5-for-1), and separating both ETFs/index trusts and **new listings (`is_new_listing = 1`)** into dedicated tables—identifies **`56`** seasoned full-universe convergence signals led by **`AMD` (`5` funds, `+$1,195,133,634` added)**, **`WFC` (`5` funds, `+$903,048,556` added)**, **`CBRE` (`5` funds, `+$268,148,933` added)**, **`FORM` (`5` funds, `+$119,590,856` added)**, and **`STX` (`4` funds, `+$1,333,294,180` added)**, while **`SPCX` (`SPACE EXPLORATION TECHNOLOGIES CORP`, `4` funds, `+$2,861,656,740` added)** leads the separate **New Listings / IPO Allocations** table.

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
- **Stock Split Detection & `yfinance` Confirmation (`src/database.py::detect_splits`)**: Corporate stock splits between `2026-Q1` and `2026-Q2` inflate post-split Q2 share counts relative to pre-split Q1 share counts. The pipeline flags candidate splits when the median implied price ratio (`Q1_price / Q2_price`) across funds is within 5% of a standard split factor `(2, 3, 4, 5, 8, 10, 15, 20, 25, 30)` and median shares move inversely, then verifies each auto-detected candidate against `yfinance` split history (`Ticker(symbol).splits`). Only **`CONFIRMED`** splits plus ground-truth `SPLIT_OVERRIDES` (`BKNG` 25-for-1, `KLAC` 10-for-1, `CVNA` 5-for-1) are applied (`25` Q1 holding rows adjusted); **`UNCONFIRMED`** candidates (`PSIG`, `LPCN`, `CURX`, `500767330`, `SLNH`, `TDUP`, `TMCI`) are logged as warnings and **not** applied.
- **Issuer-Level Share Class Merging (`SUBSTR(cusip, 1, 6)`)**: Operating common-equity share classes sharing the same 6-character CUSIP issuer number (`02079K` for `GOOGL` + `GOOG` -> `ALPHABET INC`; `71654V` for `PBR` ADRs -> `PETROLEO BRASILEIRO S A`) are merged in the convergence output, summing `total_dollars_added` across classes and counting each buying fund once (`COUNT(DISTINCT fund_id)`), while excluding non-common equity instruments (`NOTE`, `DBCV`, `PFD`, `PREF`, `DEP SHS`, `WARRANT`, `UNIT`).
- **New Listings / IPO Allocations Separation (`is_new_listing`)**: `Fact_Holdings.is_new_listing` is set to `1` when **no fund** in the database held the security in the prior quarter (`2026-Q1`). Seasoned convergence (`get_convergence_signals`) excludes `is_new_listing = 1`, while `get_new_listing_signals` reports new listings and IPO allocations (`SPCX`, `VGNT`, `ARXS`, `TGB`) in a separate table.

---

## Key Findings (Every Claim Backed by SQL Query Output)

### 1. Broad Convergence Is Dominated by Quant Funds; Discretionary Convergence (`3` Funds) Is More Informative
- **Full Universe (`min_funds = 4`, seasoned operating equities)**: **`56`** issuers met the split-adjusted buyer criteria across `4+` funds (`4` issuers with `5` buying funds and `52` with `4` buying funds). Because 4 of the 7 funds in our sample are quantitative or multi-strategy hedge funds (`Citadel Advisors`, `Two Sigma Investments`, `Renaissance Technologies`, and `Bridgewater Associates`), **`31` of the `56` signals (`55.4%`) are pure `Hedge Fund: 4` signals**, `22` have `3` hedge funds + `1` discretionary fund, and only `3` (`AMD`, `WMT`, plus none with 0 hedge funds) include `2` discretionary funds.
- **Discretionary Subset (`Conglomerate`, `Public Pension Fund`, `Sovereign Wealth Fund`, `2+` of `3` buying)**: While **the discretionary sample is only `3` funds** (`Berkshire Hathaway`, `CalPERS`, and `Temasek Holdings`), isolating this cohort surfaces **`9`** issuer-level convergence signals—**`7` of which do not appear in the 56-stock full-universe list** (`GOOGL/GOOG`, `C`, `GLW`, `NTRA`, `ATAT`, `COHR`, `UEC`; only `AMD` and `WMT` overlap). Merging Alphabet Class A (`GOOGL`, `+$9,618,617,481` added) and Class C (`GOOG`, `+$9,046,385,016` added) into a single issuer row shows that `Berkshire Hathaway` and `Temasek Holdings` added a combined **`$18,665,002,497`** in `ALPHABET INC` common stock during `2026-Q2`.
- **Source Query** (`sql/queries.sql` — Query 1 & `src/analysis.py::get_convergence_signals`):
  ```sql
  -- Full Universe (56 rows): Query 1 in sql/queries.sql (HAVING COUNT(DISTINCT qb.fund_id) >= 4)
  -- Discretionary Subset (9 rows): Query 1 filtered with AND f.fund_type IN ('Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund') HAVING COUNT(DISTINCT qb.fund_id) >= 2
  ```

### 2. Confirmed vs. Unconfirmed Stock Splits (`yfinance` Verification)
- Of the 10 candidate splits flagged by `SPLIT_OVERRIDES` and price-ratio auto-detection, **3 were confirmed** (`BKNG`, `KLAC`, `CVNA`, adjusting `25` Q1 holding rows) and **7 were marked `UNCONFIRMED`** after checking `yfinance` split history (where Q2 price changes reflected organic micro-cap drawdowns, leveraged ETF decay, or low-priced stock rallies rather than corporate split events):

| CUSIP | Ticker | Company Name | Split Type | Factor | Q1 Median Price | Q2 Median Price | Source | Confirmation Status | Split Date (`yfinance`) | Applied? |
| :--- | :--- | :--- | :--- | :---: | ---: | ---: | :--- | :--- | :--- | :---: |
| `09857L108` | `BKNG` | BOOKING HOLDINGS INC | Forward | `25:1` | `$4,525.56` | `$184.74` | `OVERRIDE` | **`CONFIRMED`** | `2026-04-02` / `2026-04-06` | **Yes** |
| `482480100` | `KLAC` | KLA CORP | Forward | `10:1` | `$1,528.50` | `$175.87` | `OVERRIDE` | **`CONFIRMED`** | `2026-06-11` / `2026-06-12` | **Yes** |
| `146869102` | `CVNA` | CARVANA CO | Forward | `5:1` | `$319.99` | `$64.59` | `AUTO` | **`CONFIRMED`** | `2026-05-08` | **Yes** |
| `G7308J113` | `PSIG` | PS INTERNATIONAL GROUP LTD | Forward | `5:1` | `$6.12` | `$1.27` | `AUTO` | `UNCONFIRMED` | None in Q2 2026 *(last: 2025-10-13)* | No |
| `53630X203` | `LPCN` | LIPOCINE INC NEW | Forward | `3:1` | `$7.99` | `$2.56` | `AUTO` | `UNCONFIRMED` | None in Q2 2026 *(last: 2023-05-12)* | No |
| `23126K106` | `CURX` | CURANEX PHARMACEUTICALS INC | Forward | `2:1` | `$0.51` | `$0.27` | `AUTO` | `UNCONFIRMED` | None | No |
| `500767330` | *(None)* | KRANESHARES 2X LONG PDD DAIL | Forward | `2:1` | `$8.85` | `$4.59` | `AUTO` | `UNCONFIRMED` | None *(leveraged ETF decay)* | No |
| `583543301` | `SLNH` | SOLUNA HLDGS INC | Reverse | `1:2` | `$0.71` | `$1.35` | `AUTO` | `UNCONFIRMED` | None in Q2 2026 *(last: 2023-10-16)* | No |
| `88556E102` | `TDUP` | THREDUP INC | Reverse | `1:2` | `$3.28` | `$6.85` | `AUTO` | `UNCONFIRMED` | None | No |
| `89455T109` | `TMCI` | TREACE MED CONCEPTS INC | Reverse | `1:3` | `$1.34` | `$3.98` | `AUTO` | `UNCONFIRMED` | None | No |

- **Source Query** (`tests/test_parse_holdings.py::test_temasek_klac_split_adjusted_change_is_zero` & `test_unconfirmed_splits_are_not_applied`):
  ```sql
  SELECT f.name, s.cusip, s.ticker, h.period, h.shares, h.qoq_change_flag
  FROM Fact_Holdings h
  JOIN Dim_Fund f ON h.fund_id = f.fund_id
  JOIN Dim_Security s ON h.security_id = s.security_id
  WHERE s.cusip IN ('09857L108', '482480100', '146869102', '88556E102') AND (h.put_call IS NULL OR h.put_call = '')
  ORDER BY s.cusip, f.name, h.period;
  ```

### 3. Why Renaissance Technologies' Implied `AMD` Price (`$559.02`) Differs From Other Funds (`$580.91`)
- **Investigation & Root Cause**: In `2026-Q2`, five funds (`CalPERS`, `Temasek Holdings`, `Two Sigma Investments`, `Bridgewater Associates`, and `Citadel Advisors`) report an implied `AMD` (`CUSIP 007903107`) price of **`$580.9100/share`**, whereas `Renaissance Technologies` reports **`$559.0212/share`** (`-3.77%` difference). Inspecting the raw SEC EDGAR XML file `data/raw/0001037389_0001037389-26-000059.xml` confirms there is only **1 `<infoTable>` row** for `AMD` in Renaissance's filing, with literal XML tags `<value>463818193</value>` and `<sshPrnamt>829697</sshPrnamt>` (`463,818,193 / 829,697 = $559.0212`). The exact same phenomenon occurs in Renaissance's `2026-Q1` filing (`0001037389_0001037389-26-000033.xml`), where its single `AMD` entry reports `<value>42841643</value>` and `<sshPrnamt>216944</sshPrnamt>` (`$197.4779/share` vs. `$203.4300` at all other funds, `-2.93%`), and across 18 other multi-venue securities in Renaissance's 13F (`STM`, `RACE`, `ASML`, `BRK-B`, `KO`, `ORCL`, etc.).
- **Why No Code Change Should Alter `value_usd`**: This is a **filer-level reporting artifact in Renaissance's raw SEC filing** (reflecting internal valuation conventions or cross-exchange share aggregation), **not** a parser or aggregation bug. Because the sum of `<value>` in Renaissance's XML equals its SEC Form 13F cover-page `<tableValueTotal>` to the exact dollar (`$72,617,871,974` in Q2; `$63,929,893,013` in Q1), modifying `value_usd` would break cover-page reconciliation (`test_cover_page_table_value_total_reconciliation`). Moreover, our split detector (`detect_splits`) uses the **cross-fund median price** (`$580.91`), making it completely immune to single-filer price outliers.
- **Source Query**:
  ```sql
  SELECT f.name, h.period, h.shares, h.value_usd, ROUND(CAST(h.value_usd AS REAL) / h.shares, 4) AS implied_price
  FROM Fact_Holdings h
  JOIN Dim_Fund f ON h.fund_id = f.fund_id
  JOIN Dim_Security s ON h.security_id = s.security_id
  WHERE s.cusip = '007903107' AND (h.put_call IS NULL OR h.put_call = '') AND h.value_usd > 0
  ORDER BY h.period, f.name;
  ```

### 4. Total Institutional AUM With and Without Options & Sector Rotation
- **Total AUM**: Across the 7 funds, total 13F AUM rose **+26.40%** from **`$1,284,805,723,954`** in `2026-Q1` to **`$1,624,015,283,814`** in `2026-Q2`. Excluding `Put`/`Call` options, common-equity AUM rose **+14.18%** from **`$803,285,214,028`** to **`$917,153,241,621`** (`$481,520,509,926` or **37.48%** options in Q1; `$706,862,042,193` or **43.53%** options in Q2).
- **Sector Coverage & Rotation**: Non-`'Unknown'` sectors cover **89.42%** of common-equity dollar value (**82.25%** of all 13F value). In `2026-Q2`, common-equity institutional capital rotated most heavily into **`Technology`** (**`+$53,218,012,069`**, **+23.13%**) and **`Financials`** (**`+$14,679,664,217`**, **+9.05%**), while rotating out of **`Energy`** (**`-$5,808,834,193`**, **-11.18%**).
- **Source Queries** (`src/analysis.py::get_aum_by_period` & `sql/queries.sql` — Query 6):
  ```sql
  SELECT period, SUM(CASE WHEN value_usd > 0 THEN value_usd ELSE 0 END) AS aum_with_options_usd,
         SUM(CASE WHEN value_usd > 0 AND (put_call IS NULL OR put_call = '') THEN value_usd ELSE 0 END) AS aum_without_options_usd
  FROM Fact_Holdings GROUP BY period ORDER BY period;
  ```

---

## Final Top 10 Convergence Signal Stocks — Q2 2026 (Full Universe, Seasoned Operating Equities, `min_funds = 4`)

*Source Query*: `sql/queries.sql` — Query 1 (`get_convergence_signals('2026-Q2', min_funds=4)`)

| Rank | CUSIP(s) | Ticker | Company Name | Sector | Funds Buying | Buying Funds | Total Dollars Added (USD) | Fund Type Breakdown |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- | ---: | :--- |
| 1 | `007903107` | `AMD` | ADVANCED MICRO DEVICES INC | Technology | 5 | CalPERS, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$1,195,133,634` | Hedge Fund: 3, Public Pension Fund: 1, Sovereign Wealth Fund: 1 |
| 2 | `949746101` | `WFC` | WELLS FARGO & CO | Financials | 5 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$903,048,556` | Hedge Fund: 4, Sovereign Wealth Fund: 1 |
| 3 | `12504L109` | `CBRE` | CBRE GROUP INC | Real Estate | 5 | Bridgewater Associates, CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$268,148,933` | Hedge Fund: 4, Public Pension Fund: 1 |
| 4 | `346375108` | `FORM` | FORMFACTOR INC | Technology | 5 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$119,590,856` | Hedge Fund: 4, Sovereign Wealth Fund: 1 |
| 5 | `G7997R103` | `STX` | SEAGATE TECHNOLOGY HLDNGS PL | Technology | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$1,333,294,180` | Hedge Fund: 3, Public Pension Fund: 1 |
| 6 | `64110L106` | `NFLX` | NETFLIX INC. | Communication Services | 4 | Citadel Advisors, Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$1,058,109,711` | Hedge Fund: 3, Sovereign Wealth Fund: 1 |
| 7 | `G5960L103` | `MDT` | MEDTRONIC PLC | Healthcare | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$815,269,329` | Hedge Fund: 4 |
| 8 | `09290D101` | `BLK` | BLACKROCK INC | Financials | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$778,654,630` | Hedge Fund: 4 |
| 9 | `931142103` | `WMT` | WALMART INC | Consumer Staples | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Temasek Holdings | `$755,714,705` | Hedge Fund: 2, Public Pension Fund: 1, Sovereign Wealth Fund: 1 |
| 10 | `45866F104` | `ICE` | INTERCONTINENTAL EXCHANGE IN | Financials | 4 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$572,770,629` | Hedge Fund: 4 |

---

## Final Discretionary Convergence Signals — Q2 2026 (`3`-Fund Sample: `Berkshire Hathaway`, `CalPERS`, `Temasek Holdings`)

*Source Query*: `get_convergence_signals('2026-Q2', fund_types=['Conglomerate', 'Public Pension Fund', 'Sovereign Wealth Fund'])`  
*(Note: Only 9 issuers in total meet the `2+` buyer threshold across the 3 discretionary funds after merging `GOOGL` and `GOOG` into a single `ALPHABET INC` row.)*

| Rank | CUSIP(s) | Ticker | Company Name | Sector | Funds Buying | Buying Funds | Total Dollars Added (USD) | In Full 4+ List? |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- | ---: | :---: |
| 1 | `02079K305/02079K107` | `GOOGL/GOOG` | ALPHABET INC | Technology | 2 | Berkshire Hathaway, Temasek Holdings | `$18,665,002,497` | No (`3` buyers overall) |
| 2 | `172967424` | `C` | CITIGROUP INC | Financials | 2 | CalPERS, Temasek Holdings | `$226,493,349` | No (`3` buyers overall) |
| 3 | `931142103` | `WMT` | WALMART INC | Consumer Staples | 2 | CalPERS, Temasek Holdings | `$224,060,786` | Yes (`4` buyers overall) |
| 4 | `007903107` | `AMD` | ADVANCED MICRO DEVICES INC | Technology | 2 | CalPERS, Temasek Holdings | `$204,656,336` | Yes (`5` buyers overall) |
| 5 | `219350105` | `GLW` | CORNING INC | Materials | 2 | CalPERS, Temasek Holdings | `$89,434,217` | No (`2` buyers overall) |
| 6 | `632307104` | `NTRA` | NATERA INC | Healthcare | 2 | CalPERS, Temasek Holdings | `$53,204,471` | No (`3` buyers overall) |
| 7 | `04965M106` | `ATAT` | ATOUR LIFESTYLE HLDGS LTD | Consumer Discretionary | 2 | CalPERS, Temasek Holdings | `$40,828,370` | No (`3` buyers overall) |
| 8 | `19247G107` | `COHR` | COHERENT CORP | Technology | 2 | CalPERS, Temasek Holdings | `$40,785,831` | No (`3` buyers overall) |
| 9 | `916896103` | `UEC` | URANIUM ENERGY CORP | Materials | 2 | CalPERS, Temasek Holdings | `$5,946,553` | No (`2` buyers overall) |

---

## Separate New Listings / IPO Allocations Table — Q2 2026 (`is_new_listing = 1`, `min_funds = 2`)

*Source Query*: `src/analysis.py::get_new_listing_signals('2026-Q2', min_funds=2)`

| Rank | CUSIP | Ticker | Company Name | Sector | `is_new_listing` | Funds Buying | Buying Funds | Total Dollars Added (USD) | Fund Type Breakdown |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: | :--- | ---: | :--- |
| 1 | `84615Q103` | `SPCX` | SPACE EXPLORATION TECHNOLOGIES CORP | Technology | `1` | 4 | Bridgewater Associates, Citadel Advisors, Temasek Holdings, Two Sigma Investments | `$2,861,656,740` | Hedge Fund: 3, Sovereign Wealth Fund: 1 |
| 2 | `92919V108` | `VGNT` | VOYAGER TECHNOLOGIES INC | Industrials | `1` | 4 | CalPERS, Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$47,816,706` | Hedge Fund: 3, Public Pension Fund: 1 |
| 3 | `03969K104` | `ARXS` | ARIS MINING CORP | Materials | `1` | 3 | Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$152,128,701` | Hedge Fund: 3 |
| 4 | `876511106` | `TGB` | TASEKO MINES LTD | Materials | `1` | 3 | Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$90,094,508` | Hedge Fund: 3 |

---

## Separate ETF & Index Trust Convergence Table — Q2 2026 (`min_funds = 3`)

*Source Query*: `src/analysis.py::get_etf_convergence_signals('2026-Q2', min_funds=3)`

| Rank | CUSIP | Ticker | ETF / Trust Name | Security Class | Funds Buying | Buying Funds | Total Dollars Added (USD) |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- | ---: |
| 1 | `464287200` | `IVV` | ISHARES CORE S&P 500 ETF | `CORE S&P500 ETF` | 4 | Bridgewater Associates, CalPERS, Citadel Advisors, Renaissance Technologies | `$20,871,368,839` |
| 2 | `78462F103` | `SPY` | STATE STR SPDR S&P 500 ETF T | `TR UNIT` | 3 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies | `$943,619,319` |
| 3 | `81369Y506` | `XLE` | ENERGY SELECT SECTOR SPDR FUND | `ST STR ENERG ETF` | 3 | Citadel Advisors, Renaissance Technologies, Two Sigma Investments | `$418,516,572` |
| 4 | `922908363` | `VOO` | VANGUARD S&P 500 ETF | `S&P 500 ETF SHS` | 3 | Bridgewater Associates, Citadel Advisors, Renaissance Technologies | `$298,268,533` |
| 5 | `92189F106` | `GDX` | VANECK GOLD MINERS ETF | `GOLD MINERS ETF` | 3 | Renaissance Technologies, Temasek Holdings, Two Sigma Investments | `$275,551,700` |

---

## Limitations

1. **Long-Only Disclosure**: Form 13F only captures long US-listed Section 13(f) equities and exchange-traded options (`Put`/`Call`). It omits short equity sales, total-return swaps, OTC derivatives, and non-US local listings—meaning a reported long equity stake may hedge an unreported short position.
2. **45-Day Reporting Delay**: Form 13F filings are submitted up to 45 calendar days after quarter-end; high-turnover managers may have already rotated out of positions disclosed at quarter-end.
3. **Quantitative Dominance vs. Small Discretionary Sample (`3` Funds)**: Broad convergence across the 7-fund universe is heavily influenced by the 4 hedge funds (`31` of `56` signals are pure `Hedge Fund: 4`), whose share increases frequently reflect market-making inventory, options delta-hedging (`$700.88B` of option notional at Citadel in `2026-Q2`), or statistical arbitrage factor turnover. While the discretionary convergence filter (`output/discretionary_signals.csv`) isolates fundamental long-horizon accumulation, **the discretionary sample in this study consists of only 3 funds** (`Berkshire Hathaway`, `CalPERS`, and `Temasek Holdings`), so a 2-fund convergence threshold represents agreement between two institutions.

---

## Conclusion

Merging multiple share classes at the 6-character CUSIP issuer level (`GOOGL/GOOG` -> `ALPHABET INC`), separating new listings (`is_new_listing = 1`, led by `SPCX` at `+$2.86B`) and ETFs (`IVV`, `SPY`), and restricting split adjustments to `yfinance`-confirmed corporate splits (`BKNG` 25-for-1, `KLAC` 10-for-1, `CVNA` 5-for-1) produces a clean institutional accumulation signal. Most importantly, comparing the 56-stock full-universe signal list (`55.4%` pure hedge-fund signals) against the 3-fund discretionary subset (`9` signals led by `GOOGL/GOOG` at `+$18.67B` and `C` at `+$226.49M`) demonstrates that separating discretionary fundamental managers from high-turnover quantitative funds is essential when interpreting 13F consensus buying.
