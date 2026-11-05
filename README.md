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
- **Dim_Security**: `security_id`, `cusip`, `ticker`, `company_name`, `sector`
- **Fact_Holdings**: `holding_id`, `fund_id`, `security_id`, `period`, `value_usd`, `shares`, `pct_of_portfolio`, `qoq_change_flag`

## Key Findings

- [Placeholder — to be completed after analysis]

## Tech Stack

- Python 3.10+
- requests
- pandas
- lxml
- sqlite3 (built-in)
- python-dotenv

## Disclaimer

13F data is 45 days delayed and for educational purposes only.
