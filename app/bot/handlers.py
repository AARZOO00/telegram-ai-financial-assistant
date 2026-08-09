import os
import base64
import tempfile
import asyncio
from io import BytesIO
import pypdf
from telegram import Update
from telegram.ext import ContextTypes
import openai

from app.db.database import SessionLocal
from app.ai.ai_service import process_message

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler."""
    user = update.effective_user
    db = SessionLocal()
    try:
        reply = await asyncio.to_thread(
            process_message,
            db=db,
            telegram_id=user.id,
            user_name=user.first_name,
            content="Hello! I am a new user."
        )
        await update.message.reply_text(reply)
    finally:
        db.close()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle normal text messages."""
    user = update.effective_user
    text = update.message.text
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    db = SessionLocal()
    try:
        reply = await asyncio.to_thread(
            process_message,
            db=db,
            telegram_id=user.id,
            user_name=user.first_name,
            content=text
        )
        await update.message.reply_text(reply)
    finally:
        db.close()

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages using OpenAI Whisper."""
    user = update.effective_user
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        voice_file = await update.message.voice.get_file()
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
            await voice_file.download_to_drive(custom_path=tmp_file.name)
            tmp_file_path = tmp_file.name
            
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        with open(tmp_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
            
        text = transcript.text
        os.remove(tmp_file_path)
        
        db = SessionLocal()
        try:
            reply = await asyncio.to_thread(
                process_message,
                db=db,
                telegram_id=user.id,
                user_name=user.first_name,
                content=text
            )
            await update.message.reply_text(f"(Transcription: {text})\n\n{reply}")
        finally:
            db.close()
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        await update.message.reply_text("I couldn't process your voice message right now.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image messages."""
    user = update.effective_user
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        photo = update.message.photo[-1]
        photo_file = await photo.get_file()
        
        out_stream = BytesIO()
        await photo_file.download_to_memory(out_stream)
        out_stream.seek(0)
        
        image_data = base64.b64encode(out_stream.read()).decode("utf-8")
        caption = update.message.caption or "Please analyze this image."
        
        db = SessionLocal()
        try:
            reply = await asyncio.to_thread(
                process_message,
                db=db,
                telegram_id=user.id,
                user_name=user.first_name,
                content=caption,
                image_media_type="image/jpeg",
                image_data=image_data
            )
            await update.message.reply_text(reply)
        finally:
            db.close()
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        await update.message.reply_text("I couldn't process your image right now.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PDF documents."""
    user = update.effective_user
    doc = update.message.document
    
    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("I can only read PDF documents right now.")
        return
        
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        doc_file = await doc.get_file()
        
        out_stream = BytesIO()
        await doc_file.download_to_memory(out_stream)
        out_stream.seek(0)
        
        pdf_reader = pypdf.PdfReader(out_stream)
        extracted_text = ""
        for i, page in enumerate(pdf_reader.pages):
            if i > 20:
                extracted_text += "\n[... truncated after 20 pages ...]"
                break
            extracted_text += page.extract_text() + "\n"
            
        caption = update.message.caption or "I uploaded a document for you to analyze."
        
        db = SessionLocal()
        try:
            reply = await asyncio.to_thread(
                process_message,
                db=db,
                telegram_id=user.id,
                user_name=user.first_name,
                content=caption,
                pdf_text=extracted_text
            )
            await update.message.reply_text(reply)
        finally:
            db.close()
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        await update.message.reply_text("I couldn't extract text from this document.")
