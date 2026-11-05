<!-- Template — complete after running analysis.py -->
# Smart Money Convergence Analysis — Q[X] 20[XX]

**Author**: Muhammad Kamal
**Date**: [Date]
**Data Source**: SEC EDGAR 13F-HR Filings

## Executive Summary
[2-3 sentence summary of key findings — to be completed]

## Data & Methodology
Institutional investment managers with over $100 million in qualifying assets are required to file Form 13F within 45 days of the end of each calendar quarter. The data in this report is sourced directly from SEC EDGAR filings and reflects positions held as of the end of the specified quarter.

We analyzed 7 major funds for this report: Berkshire Hathaway, Renaissance Technologies, Citadel Advisors, Two Sigma Investments, D.E. Shaw, Baupost Group, and Bridgewater Associates. 

The core of our methodology is the **convergence threshold**: we flag any security where 3 or more of these independent funds either initiated a new position or increased their existing position during the same quarter. This filters out isolated moves and highlights true consensus institutional buying. Raw filings provide CUSIP identifiers, which we mapped to human-readable tickers using the OpenFIGI API.

## Key Findings
- [bullet list — to be completed after analysis]

## Convergence Signal Stocks — Q[X] 20[XX]

| Ticker | Company | Sector | Funds Buying | Total Value USD | Consensus Signal |
|--------|---------|--------|--------------|-----------------|------------------|
| [TICKER] | [Company Name] | [Sector] | [Count] | [$$] | [Strong/Moderate] |

## Notable New Positions
- [to be completed]

## Risk Considerations
- **45-Day Delay**: 13F filings are delayed by up to 45 days after the quarter ends. Managers may have already exited or altered these positions by the time filings become public.
- **Survivorship Bias**: The analysis only reflects current holdings, not positions entered and exited entirely within the same quarter.
- **Lack of Short Positions**: 13F filings only mandate disclosure of long equity positions and certain options (puts/calls). They do not provide a complete view of a manager's net exposure or short positions. Position sizes are not always disclosed at a granular level.

## Conclusion
[to be completed]
