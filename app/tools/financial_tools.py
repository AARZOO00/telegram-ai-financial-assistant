import yfinance as yf
from duckduckgo_search import DDGS
import requests
import json
import os
from datetime import datetime

def get_stock_price(ticker: str) -> str:
    """Get current stock price, % change, and volume for a ticker.
    
    Args:
        ticker: The stock ticker symbol, e.g., AAPL, MSFT
    """
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="5d")
        if data.empty:
            return f"Could not find data for ticker {ticker}."
        
        current_price = data['Close'].iloc[-1]
        prev_price = data['Close'].iloc[-2] if len(data) > 1 else current_price
        change_pct = ((current_price - prev_price) / prev_price) * 100
        volume = data['Volume'].iloc[-1]
        
        return json.dumps({
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "change_percent": round(change_pct, 2),
            "volume": int(volume)
        })
    except Exception as e:
        return f"Error fetching stock price: {str(e)}"

def get_company_news(company_name: str, days: int = 7) -> str:
    """Get recent news headlines for a company.
    
    Args:
        company_name: The name of the company or ticker
        days: Number of days to look back for news (default 7)
    """
    try:
        ddgs = DDGS()
        # timelimit: d (day), w (week), m (month)
        timelimit = "w" if days <= 7 else "m" if days <= 30 else None
        results = ddgs.news(company_name, max_results=5, timelimit=timelimit)
        
        if not results:
            return f"No recent news found for {company_name}."
            
        news_items = [{"title": r['title'], "source": r['source'], "date": r['date']} for r in results]
        return json.dumps(news_items)
    except Exception as e:
        return f"Error fetching news: {str(e)}"

def get_sec_filings(ticker: str) -> str:
    """Get recent SEC filings for a ticker using the EDGAR API.
    
    Args:
        ticker: The stock ticker symbol
    """
    try:
        # User-Agent is required by SEC API
        headers = {
            "User-Agent": os.environ.get("SEC_USER_AGENT", "test_bot@example.com")
        }
        # Get CIK for ticker
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        response = requests.get(tickers_url, headers=headers)
        if response.status_code != 200:
            return "Failed to fetch ticker mapping from SEC."
            
        tickers_data = response.json()
        cik = None
        for key, value in tickers_data.items():
            if value['ticker'].upper() == ticker.upper():
                cik = str(value['cik_str']).zfill(10)
                break
                
        if not cik:
            return f"Could not find SEC CIK for ticker {ticker}."
            
        # Get recent submissions
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        sub_response = requests.get(submissions_url, headers=headers)
        if sub_response.status_code != 200:
            return "Failed to fetch filings from SEC."
            
        sub_data = sub_response.json()
        filings = sub_data.get("filings", {}).get("recent", {})
        
        recent_filings = []
        if filings and "form" in filings:
            for i in range(min(5, len(filings["form"]))):
                recent_filings.append({
                    "form": filings["form"][i],
                    "filingDate": filings["filingDate"][i],
                    "reportDate": filings["reportDate"][i],
                    "accessionNumber": filings["accessionNumber"][i]
                })
                
        return json.dumps(recent_filings)
    except Exception as e:
        return f"Error fetching SEC filings: {str(e)}"

def web_search(query: str) -> str:
    """Perform a general web search for information, earnings dates, ratings, etc.
    
    Args:
        query: The search query string
    """
    try:
        ddgs = DDGS()
        results = ddgs.text(query, max_results=5)
        if not results:
            return f"No results found for '{query}'."
            
        search_items = [{"title": r['title'], "body": r['body'], "href": r['href']} for r in results]
        return json.dumps(search_items)
    except Exception as e:
        return f"Error performing web search: {str(e)}"

CLAUDE_TOOLS = [
    {
        "name": "get_stock_price",
        "description": "Get current stock price, percentage change, and trading volume for a given ticker symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol, e.g., AAPL, MSFT"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_company_news",
        "description": "Get recent news headlines for a given company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The name of the company or ticker"
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back for news (default 7)"
                }
            },
            "required": ["company_name"]
        }
    },
    {
        "name": "get_sec_filings",
        "description": "Get recent SEC filings (like 10-K, 10-Q, 8-K) for a given stock ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the web for general information, earnings dates, analyst ratings, or macro events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "update_user_preference",
        "description": "Update the user's preferences based on the conversation (e.g., sectors followed, roles, briefing times).",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The preference key, e.g., 'role', 'watched_companies', 'briefing_time'"
                },
                "value": {
                    "type": "string",
                    "description": "The value for the preference, could be a comma-separated list"
                }
            },
            "required": ["key", "value"]
        }
    }
]

def execute_tool(name: str, args: dict) -> str:
    """Execute a tool by name with arguments."""
    if name == "get_stock_price":
        return get_stock_price(args.get("ticker"))
    elif name == "get_company_news":
        return get_company_news(args.get("company_name"), args.get("days", 7))
    elif name == "get_sec_filings":
        return get_sec_filings(args.get("ticker"))
    elif name == "web_search":
        return web_search(args.get("query"))
    else:
        return f"Tool {name} not found or not executable here."
