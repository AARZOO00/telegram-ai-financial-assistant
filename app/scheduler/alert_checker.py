import json
import asyncio
import yfinance as yf
from app.db.database import SessionLocal
from app.db.models import User

# In-memory deduplication cache for the day
ALERTS_SENT = set()

async def check_alerts(bot):
    """Check for >5% moves in watched tickers."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            prefs = user.preferences_json or {}
            watched_raw = prefs.get('watched_companies', '')
            
            if not watched_raw:
                continue
                
            tickers = [t.strip() for t in watched_raw.split(',')]
            
            for ticker in tickers:
                if len(ticker) > 5 or ' ' in ticker:
                    continue
                    
                alert_key = f"{user.telegram_id}_{ticker}"
                if alert_key in ALERTS_SENT:
                    continue
                    
                try:
                    stock = yf.Ticker(ticker)
                    data = await asyncio.to_thread(stock.history, period="2d")
                    if len(data) >= 2:
                        current = data['Close'].iloc[-1]
                        prev = data['Close'].iloc[-2]
                        pct_change = ((current - prev) / prev) * 100
                        
                        if abs(pct_change) >= 5.0:
                            direction = "UP" if pct_change > 0 else "DOWN"
                            msg = f"🚨 ALERT: {ticker} is {direction} {abs(pct_change):.2f}% today!"
                            await bot.send_message(chat_id=user.telegram_id, text=msg)
                            ALERTS_SENT.add(alert_key)
                except Exception as e:
                    print(f"Error checking alert for {ticker}: {e}")
    finally:
        db.close()
