-- 1. Smart Money Convergence Signal (2026-Q2):
-- Identifies common-equity securities accumulated by 4 or more independent institutions in the same quarter.
-- A fund qualifies as a buyer only if the position is newly initiated or its share count grew by >=10% QoQ
-- and the dollar value of shares added (shares_added * Q2 price) is at least $1,000,000, filtering out price drift and noise.
WITH prior_period AS (
    SELECT MAX(period) AS prev_period
    FROM Fact_Holdings
    WHERE period < '2026-Q2'
),
qualified_buyers AS (
    SELECT
        h.security_id,
        s.cusip,
        s.ticker,
        s.company_name,
        s.sector,
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
      AND (
          h.qoq_change_flag = 'NEW'
          OR (prev.shares > 0 AND (h.shares - prev.shares) * 1.0 / prev.shares >= 0.10)
      )
      AND ((h.shares - COALESCE(prev.shares, 0)) * (CAST(h.value_usd AS REAL) / h.shares)) >= 1000000
),
type_breakdown AS (
    SELECT
        security_id,
        GROUP_CONCAT(type_label, ', ') AS fund_type_breakdown
    FROM (
        SELECT
            security_id,
            fund_type || ': ' || COUNT(DISTINCT fund_id) AS type_label
        FROM qualified_buyers
        GROUP BY security_id, fund_type
        ORDER BY security_id, COUNT(DISTINCT fund_id) DESC, fund_type ASC
    )
    GROUP BY security_id
)
SELECT
    qb.cusip,
    qb.ticker,
    qb.company_name,
    qb.sector,
    COUNT(DISTINCT qb.fund_id) AS funds_buying,
    GROUP_CONCAT(qb.fund_name, ', ') AS funds,
    CAST(ROUND(SUM(qb.added_value_usd), 0) AS INTEGER) AS total_dollars_added,
    tb.fund_type_breakdown
FROM (SELECT * FROM qualified_buyers ORDER BY fund_name) qb
JOIN type_breakdown tb ON qb.security_id = tb.security_id
GROUP BY qb.security_id, qb.cusip, qb.ticker, qb.company_name, qb.sector, tb.fund_type_breakdown
HAVING COUNT(DISTINCT qb.fund_id) >= 4
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

