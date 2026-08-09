import os
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

from app.db.database import engine, Base
from app.bot.handlers import start_command, handle_text, handle_voice, handle_photo, handle_document
from app.scheduler.daily_brief import run_daily_brief
from app.scheduler.alert_checker import check_alerts

# Create DB tables
Base.metadata.create_all(bind=engine)

# Init Telegram App
bot_app = Application.builder().token(os.environ.get("TELEGRAM_BOT_TOKEN", "dummy_token")).build()

# Setup handlers
bot_app.add_handler(CommandHandler("start", start_command))
bot_app.add_handler(MessageHandler(filters.VOICE, handle_voice))
bot_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
bot_app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_BOT_TOKEN") != "dummy_token":
        # Initialize and start bot
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        
        # Setup scheduler
        scheduler.add_job(run_daily_brief, 'cron', hour=8, minute=0, args=[bot_app.bot])
        scheduler.add_job(check_alerts, 'interval', minutes=15, args=[bot_app.bot])
        scheduler.start()
        
        print("Bot and Scheduler started.")
    else:
        print("No TELEGRAM_BOT_TOKEN provided. Bot not started.")
        
    yield
    
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_BOT_TOKEN") != "dummy_token":
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
        scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
