-- Convergence Signal: stocks bought by 3+ funds in the same quarter (main thesis query)
SELECT 
    s.ticker, 
    s.company_name, 
    s.sector,
    COUNT(DISTINCT f.fund_id) AS funds_buying,
    SUM(h.value_usd) AS total_value_usd
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
JOIN Dim_Fund f ON h.fund_id = f.fund_id
WHERE h.period = '2024-Q2' 
  AND h.qoq_change_flag IN ('NEW', 'INCREASED')
GROUP BY s.security_id, s.ticker, s.company_name, s.sector
HAVING COUNT(DISTINCT f.fund_id) >= 3
ORDER BY funds_buying DESC, total_value_usd DESC;

-- QoQ New Positions: CUSIPs appearing for the first time this quarter vs last quarter
SELECT 
    f.name AS fund_name,
    s.ticker,
    s.company_name,
    h.value_usd,
    h.pct_of_portfolio
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
JOIN Dim_Fund f ON h.fund_id = f.fund_id
WHERE h.period = '2024-Q2' 
  AND h.qoq_change_flag = 'NEW'
ORDER BY h.value_usd DESC;

-- QoQ Exited Positions: CUSIPs present last quarter but absent this quarter
-- (Note: 'EXITED' flag implies a placeholder record was generated or tracked elsewhere)
SELECT 
    f.name AS fund_name,
    s.ticker,
    s.company_name
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
JOIN Dim_Fund f ON h.fund_id = f.fund_id
WHERE h.period = '2024-Q2' 
  AND h.qoq_change_flag = 'EXITED';

-- Top Holdings by Total Institutional AUM: ranked by sum of value_usd across all funds
SELECT 
    s.ticker, 
    s.company_name, 
    SUM(h.value_usd) AS total_aum
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
WHERE h.period = '2024-Q2'
GROUP BY s.security_id, s.ticker, s.company_name
ORDER BY total_aum DESC
LIMIT 20;

-- Fund Concentration: top 10 positions as % of a specific fund's total portfolio
SELECT 
    s.ticker,
    s.company_name,
    h.value_usd,
    h.pct_of_portfolio
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
JOIN Dim_Fund f ON h.fund_id = f.fund_id
WHERE f.name = 'Bridgewater Associates' 
  AND h.period = '2024-Q2'
ORDER BY h.pct_of_portfolio DESC
LIMIT 10;

-- Sector Rotation: total value_usd grouped by sector, compared across two periods
SELECT 
    s.sector,
    SUM(CASE WHEN h.period = '2024-Q1' THEN h.value_usd ELSE 0 END) AS prev_qtr_value,
    SUM(CASE WHEN h.period = '2024-Q2' THEN h.value_usd ELSE 0 END) AS curr_qtr_value,
    (SUM(CASE WHEN h.period = '2024-Q2' THEN h.value_usd ELSE 0 END) - 
     SUM(CASE WHEN h.period = '2024-Q1' THEN h.value_usd ELSE 0 END)) AS value_change
FROM Fact_Holdings h
JOIN Dim_Security s ON h.security_id = s.security_id
WHERE h.period IN ('2024-Q1', '2024-Q2')
GROUP BY s.sector
ORDER BY value_change DESC;
