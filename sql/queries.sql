-- 1. Smart Money Convergence Signal (2026-Q2):
-- Identifies operating-equity issuers accumulated by 4 or more independent institutions in the same quarter (excluding options, ETFs, and "New to the sample (no prior-quarter holders)" rows).
-- Merges multiple share classes at the 6-character CUSIP issuer level (e.g., GOOGL+GOOG -> one Alphabet row), summing dollars added and counting each fund once.
-- A fund qualifies as a buyer only if the position is newly initiated or its split-adjusted share count grew by >=10% QoQ and added value >= $1,000,000.
WITH prior_period AS (
    SELECT MAX(period) AS prev_period
    FROM Fact_Holdings
    WHERE period < '2026-Q2'
),
qualified_buyers AS (
    SELECT
        SUBSTR(s.cusip, 1, 6) AS issuer_id,
        h.security_id,
        s.cusip,
        s.ticker,
        s.company_name,
        s.sector,
        COALESCE(h.is_new_listing, 0) AS is_new_listing,
        f.fund_id,
        f.name AS fund_name,
        f.fund_type,
        (h.shares - COALESCE(prev.shares, 0)) * (CAST(h.value_usd AS REAL) / h.shares) AS added_value_usd
    FROM Fact_Holdings h
    JOIN Dim_Security s ON h.security_id = s.security_id
    JOIN Dim_Fund f ON h.fund_id = f.fund_id
    LEFT JOIN Fact_Holdings prev
        ON prev.fund_id = h.fund_id
       AND prev.security_id = h.security_id
       AND COALESCE(prev.put_call, '') = COALESCE(h.put_call, '')
       AND prev.period = (SELECT prev_period FROM prior_period)
       AND prev.value_usd > 0
    WHERE h.period = '2026-Q2'
      AND (h.put_call IS NULL OR h.put_call = '')
      AND h.value_usd > 0
      AND h.shares > 0
      AND COALESCE(h.is_new_listing, 0) = 0
      AND (
          h.qoq_change_flag = 'NEW'
          OR (prev.shares > 0 AND (h.shares - prev.shares) * 1.0 / prev.shares >= 0.10)
      )
      AND ((h.shares - COALESCE(prev.shares, 0)) * (CAST(h.value_usd AS REAL) / h.shares)) >= 1000000
      AND NOT (
          UPPER(COALESCE(s.company_name, '')) LIKE '%ISHARES%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%SPDR%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%VANGUARD%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%INVESCO%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%PROSHARES%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%DIREXION%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%VANECK%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%WISDOMTREE%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%SCHWAB STRATEGIC%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%FIRST TR%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%GLOBAL X%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%ARK ETF%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '% ETF%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE 'ETF %'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%INDEX FD%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%INDEX FUND%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%INDEX TRUST%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%EXCHANGE TRADED%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%EXCH TRADED%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%SERIES TRUST%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%COVINGTON TRUST%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%FLEXSHARES%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%PACER FDS%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%TIDAL TRUST%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%VICTORY PORTFOLIOS%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%KRANESHARES%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%INVESTMENTS ET%'
          OR UPPER(COALESCE(s.company_name, '')) LIKE '%PIMCO EQUITY%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%ETF%'
          OR UPPER(COALESCE(s.ticker, '')) IN (
              'IVV', 'SPY', 'VOO', 'QQQ', 'IWM', 'DIA', 'EEM', 'TLT', 'GLD', 'SLV',
              'HYG', 'LQD', 'XLF', 'XLK', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU', 'XLY',
              'XLB', 'XLC', 'XLRE', 'SMH', 'SOXX', 'EWZ', 'FXI', 'KWEB', 'ARKK',
              'IBIT', 'FBTC', 'GBTC', 'ETHA', 'BITO', 'VTI', 'VEA', 'VWO', 'IEFA',
              'EFA', 'AGG', 'BND', 'JNK', 'EMB', 'TIP', 'SHY', 'IEF', 'GOVT', 'MUB',
              'RSP', 'MDY', 'IJR', 'IJH', 'IWF', 'IWD', 'IWO', 'IWN', 'ACWI', 'VXUS',
              'URA', 'USO', 'UNG', 'KBE', 'KRE', 'XBI', 'XME', 'RWL', 'GDX', 'GDXJ'
          )
      )
      AND NOT (
          UPPER(COALESCE(s.security_class, '')) LIKE '%NOTE%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%DBCV%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%DEBT%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%PFD%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%PREF%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%DEP SHS%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%DEP CM%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%DEP CUM%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%W EXP%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%WARRANT%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%RIGHT%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%UNIT%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%MICROSCTR%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%CAL LKD%'
          OR UPPER(COALESCE(s.security_class, '')) LIKE '%NT LKD%'
      )
),
type_breakdown AS (
    SELECT
        issuer_id,
        GROUP_CONCAT(type_label, ', ') AS fund_type_breakdown
    FROM (
        SELECT
            issuer_id,
            fund_type || ': ' || COUNT(DISTINCT fund_id) AS type_label
        FROM qualified_buyers
        GROUP BY issuer_id, fund_type
        ORDER BY issuer_id, COUNT(DISTINCT fund_id) DESC, fund_type ASC
    )
    GROUP BY issuer_id
),
issuer_meta AS (
    SELECT
        issuer_id,
        REPLACE(GROUP_CONCAT(DISTINCT cusip), ',', '/') AS cusip,
        REPLACE(GROUP_CONCAT(DISTINCT ticker), ',', '/') AS ticker,
        CASE
            WHEN COUNT(DISTINCT cusip) > 1 THEN
                TRIM(
                    REPLACE(
                        REPLACE(
                            REPLACE(
                                REPLACE(MIN(company_name), '-CL A', ''),
                                '-CL C', ''
                            ),
                            '- B SHS', ''
                        ),
                        '-A', ''
                    )
                )
            ELSE MIN(company_name)
        END AS company_name,
        MAX(sector) AS sector,
        MIN(is_new_listing) AS is_new_listing
    FROM (SELECT * FROM qualified_buyers ORDER BY cusip DESC)
    GROUP BY issuer_id
),
issuer_funds AS (
    SELECT
        issuer_id,
        COUNT(DISTINCT fund_id) AS funds_buying,
        REPLACE(GROUP_CONCAT(DISTINCT fund_name), ',', ', ') AS funds
    FROM (SELECT * FROM qualified_buyers ORDER BY fund_name ASC)
    GROUP BY issuer_id
)
SELECT
    im.cusip,
    im.ticker,
    im.company_name,
    im.sector,
    im.is_new_listing,
    ifd.funds_buying,
    ifd.funds,
    CAST(ROUND(SUM(qb.added_value_usd), 0) AS INTEGER) AS total_dollars_added,
    tb.fund_type_breakdown
FROM qualified_buyers qb
JOIN issuer_meta im ON qb.issuer_id = im.issuer_id
JOIN issuer_funds ifd ON qb.issuer_id = ifd.issuer_id
JOIN type_breakdown tb ON qb.issuer_id = tb.issuer_id
GROUP BY qb.issuer_id, im.cusip, im.ticker, im.company_name, im.sector, im.is_new_listing, ifd.funds_buying, ifd.funds, tb.fund_type_breakdown
HAVING ifd.funds_buying >= 4
ORDER BY funds_buying DESC, total_dollars_added DESC;

-- 2. QoQ New Positions (2026-Q2):
-- Lists all newly initiated holdings in 2026-Q2 that were absent from the same fund's 2026-Q1 filing.
-- Ranked by dollar value descending to highlight the highest-conviction fresh entries across the institutional sample.
SELECT
    f.name AS fund_name,
    f.fund_type,
    s.cusip,
    s.ticker,
    s.company_name,
    s.sector,
    h.put_call,
    h.value_usd,
    h.shares,
    h.pct_of_portfolio
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
JOIN Dim_Fund f ON h.fund_id = f.fund_id
WHERE h.period = '2026-Q2'
  AND h.qoq_change_flag = 'NEW'
  AND h.value_usd > 0
ORDER BY h.value_usd DESC;

-- 3. QoQ Exited Positions (2026-Q2):
-- Lists all holdings that a fund held in 2026-Q1 but completely liquidated by the end of 2026-Q2.
-- Joins back to the 2026-Q1 row to surface the prior-quarter dollar value and share count of each exited stake.
WITH prior_period AS (
    SELECT MAX(period) AS prev_period
    FROM Fact_Holdings
    WHERE period < '2026-Q2'
)
SELECT
    f.name AS fund_name,
    f.fund_type,
    s.cusip,
    s.ticker,
    s.company_name,
    s.sector,
    h.put_call,
    prev.value_usd AS prior_value_usd,
    prev.shares AS prior_shares,
    prev.pct_of_portfolio AS prior_pct_of_portfolio
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
JOIN Dim_Fund f ON h.fund_id = f.fund_id
LEFT JOIN Fact_Holdings prev
    ON prev.fund_id = h.fund_id
   AND prev.security_id = h.security_id
   AND COALESCE(prev.put_call, '') = COALESCE(h.put_call, '')
   AND prev.period = (SELECT prev_period FROM prior_period)
WHERE h.period = '2026-Q2'
  AND h.qoq_change_flag = 'EXITED'
ORDER BY prev.value_usd DESC;

-- 4. Top Holdings by Total Institutional AUM (2026-Q2):
-- Aggregates active common-equity holdings across all 7 funds to rank the top 20 consensus positions by combined dollar value.
-- Excludes option contracts and exited placeholder rows so the ranking reflects true underlying equity ownership.
SELECT
    s.cusip,
    s.ticker,
    s.company_name,
    s.sector,
    SUM(h.value_usd) AS total_aum,
    COUNT(DISTINCT h.fund_id) AS funds_holding,
    GROUP_CONCAT(DISTINCT f.name) AS holding_funds
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
JOIN Dim_Fund f ON h.fund_id = f.fund_id
WHERE h.period = '2026-Q2'
  AND (h.put_call IS NULL OR h.put_call = '')
  AND (h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED')
  AND h.value_usd > 0
GROUP BY s.security_id, s.cusip, s.ticker, s.company_name, s.sector
ORDER BY total_aum DESC
LIMIT 20;

-- 5. Fund Concentration (Berkshire Hathaway, 2026-Q2):
-- Returns the top 10 active holdings for a specific institution along with each position's share of total fund AUM.
-- Used to measure portfolio concentration and compare high-conviction discretionary managers against diversified quants.
SELECT
    s.cusip,
    s.ticker,
    s.company_name,
    s.sector,
    h.put_call,
    h.value_usd,
    h.shares,
    h.pct_of_portfolio,
    h.qoq_change_flag
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
JOIN Dim_Fund f ON h.fund_id = f.fund_id
WHERE f.name = 'Berkshire Hathaway'
  AND h.period = '2026-Q2'
  AND (h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED')
  AND h.value_usd > 0
ORDER BY h.value_usd DESC
LIMIT 10;

-- 6. Sector Rotation (2026-Q1 vs 2026-Q2):
-- Compares total common-equity institutional AUM and portfolio weight by SIC-mapped sector across 2026-Q1 and 2026-Q2.
-- Reveals where aggregate institutional capital rotated quarter-over-quarter in both absolute dollars and basis points.
SELECT
    s.sector,
    SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END) AS q1_equity_aum_usd,
    SUM(CASE WHEN h.period = '2026-Q2' THEN h.value_usd ELSE 0 END) AS q2_equity_aum_usd,
    (SUM(CASE WHEN h.period = '2026-Q2' THEN h.value_usd ELSE 0 END) -
     SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END)) AS qoq_dollar_change_usd,
    ROUND(
        (SUM(CASE WHEN h.period = '2026-Q2' THEN h.value_usd ELSE 0 END) -
         SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END)) * 100.0
        / NULLIF(SUM(CASE WHEN h.period = '2026-Q1' THEN h.value_usd ELSE 0 END), 0),
        2
    ) AS qoq_pct_change
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
WHERE h.period IN ('2026-Q1', '2026-Q2')
  AND (h.put_call IS NULL OR h.put_call = '')
  AND (h.qoq_change_flag IS NULL OR h.qoq_change_flag != 'EXITED')
  AND h.value_usd > 0
GROUP BY s.sector
ORDER BY qoq_dollar_change_usd DESC;

