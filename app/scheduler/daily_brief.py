import asyncio
from app.db.database import SessionLocal
from app.db.models import User
from app.ai.ai_service import process_message

async def run_daily_brief(bot):
    """Run daily brief for all users based on their preferences."""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            prefs = user.preferences_json or {}
            watched = prefs.get('watched_companies') or prefs.get('sectors')
            if watched:
                prompt = f"It is morning. Generate a daily brief based on my watched companies/sectors: {watched}. ONLY if something genuinely moved/matters today. If nothing significant happened, return exactly 'NOTHING' with no other text."
                
                reply = await asyncio.to_thread(
                    process_message,
                    db=db,
                    telegram_id=user.telegram_id,
                    user_name=user.name,
                    content=prompt
                )
                
                if reply.strip() != "NOTHING" and "NOTHING" not in reply:
                    try:
                        await bot.send_message(chat_id=user.telegram_id, text=f"🌅 Daily Brief:\n\n{reply}")
                    except Exception as e:
                        print(f"Failed to send brief to {user.telegram_id}: {e}")
    finally:
        db.close()
