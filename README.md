# Telegram AI Financial Assistant

A complete, deployable Telegram bot powered by Groq's Llama 3.3 70B Versatile model, providing natural conversation, financial data retrieval, and scheduled alerts. 

## Features
- **Conversational Memory**: Chat naturally with Llama 3, which remembers your previous messages.
- **Onboarding**: The bot will ask you about your role, favorite sectors, and preferred briefing time.
- **Financial Tools**: Llama 3 can autonomously use tools to fetch stock prices (yfinance), recent news (DuckDuckGo), and SEC filings (EDGAR API).
- **Web Search**: Llama 3 can browse the web for general financial information.
- **Voice Support**: Send voice notes and the bot will transcribe them using OpenAI Whisper.
- **Image Support**: Send photos of charts or documents for Groq's Llama 3.2 Vision model to analyze.
- **Document Intelligence**: Upload PDFs (like 10-K or earnings decks) and ask questions about them.
- **Proactive Alerts & Briefings**: Get daily morning briefs and alerts for >5% moves on your watched stocks.

## Setup Instructions

1. Clone or download this project.
2. Ensure you have Python 3.9+ installed.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up your environment variables:
   Copy `.env.example` to `.env` and fill in your keys:
   - `TELEGRAM_BOT_TOKEN`: From BotFather on Telegram.
   - `GROQ_API_KEY`: For Groq API.
   - `OPENAI_API_KEY`: For Whisper voice transcription.
   - `SEC_USER_AGENT`: Your email for the SEC API (e.g., `you@example.com`).

5. Run the bot locally:
   ```bash
   python main.py
   ```
   Or using uvicorn:
   ```bash
   uvicorn main:app --reload
   ```

## Deployment (Railway/Render)

This project uses FastAPI as its shell, making it extremely easy to deploy on platforms like Railway or Render.

### Railway
1. Push this code to a GitHub repository.
2. Create a new project on Railway and connect your GitHub repo.
3. Railway will automatically detect the Python environment and `requirements.txt`.
4. Add your Environment Variables in the Railway dashboard.
5. In your Railway service settings, set the Start Command to:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
6. The bot will run continuously, using polling mode to communicate with Telegram and APScheduler to handle daily briefs and alerts.

## Project Structure
- `app/bot/`: Telegram message handlers (text, voice, photo, pdf).
- `app/ai/`: Groq conversation and tool orchestration logic.
- `app/tools/`: The financial data tools the AI can call.
- `app/db/`: SQLite database models and setup using SQLAlchemy.
- `app/scheduler/`: APScheduler tasks for daily briefs and price alerts.
- `main.py`: The entrypoint that starts FastAPI, the bot, and the scheduler.
