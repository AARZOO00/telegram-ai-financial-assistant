import os
from dotenv import load_dotenv
load_dotenv()

from app.db.database import SessionLocal
from app.ai.ai_service import process_message

db = SessionLocal()
print("Sending test message...")
reply = process_message(db, 123456789, "TestUser", "What is AAPL stock price right now?")
print("Reply:", reply)
db.close()
