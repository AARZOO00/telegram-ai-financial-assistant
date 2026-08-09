import os
import json
import time
import traceback
import re
from groq import Groq
from sqlalchemy.orm import Session
from app.db.models import User, Message
from app.tools.financial_tools import get_stock_price, get_company_news, get_sec_filings, web_search

MODEL_NAME = "llama-3.3-70b-versatile"
VISION_MODEL_NAME = "llama-3.2-90b-vision-preview"

SYSTEM_PROMPT = """You are an experienced financial analyst and executive assistant. Be concise, natural, and conversational. Never use bullet-point dumps unless genuinely useful. Ask clarifying questions when a request is ambiguous (e.g. 'Tell me about Apple' -> ask if they want news, financials, valuation, or filings).
For new users, naturally ask 2-3 onboarding questions in ONE flowing conversation (not a form): ask about their role, companies/sectors followed, and preferred briefing time. They can say 'skip' anytime."""

# Define tools in OpenAI JSON schema format
GROQ_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get current stock price, % change, and volume for a ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "The stock ticker symbol, e.g., AAPL, MSFT"
                    }
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_news",
            "description": "Get recent news headlines for a company.",
            "parameters": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_sec_filings",
            "description": "Get recent SEC filings for a ticker using the EDGAR API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "The stock ticker symbol"
                    }
                },
                "required": ["ticker"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Perform a general web search for information, earnings dates, ratings, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_user_preference",
            "description": "Update the user's preferences based on the conversation.",
            "parameters": {
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
    }
]

TOOLS_MAP = {
    "get_stock_price": get_stock_price,
    "get_company_news": get_company_news,
    "get_sec_filings": get_sec_filings,
    "web_search": web_search
}

groq_client = None

def get_groq_client():
    global groq_client
    if groq_client is None:
        groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return groq_client

def process_message(db: Session, telegram_id: int, user_name: str, content: str, image_media_type=None, image_data=None, pdf_text=None) -> str:
    client = get_groq_client()
    
    # 1. Get or Create User
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id, name=user_name, preferences_json={})
        db.add(user)
        db.commit()
        db.refresh(user)
        
    # 2. Save user message
    db_content = content
    if image_data:
        db_content = f"[Image Attached] {content}"
    if pdf_text:
        db_content = f"[PDF Attached] {content}"
        
    user_msg = Message(user_id=user.id, role="user", content=db_content)
    db.add(user_msg)
    db.commit()
    
    # 3. Retrieve history (last 20 messages)
    history = db.query(Message).filter(Message.user_id == user.id).order_by(Message.timestamp.desc()).limit(20).all()
    history.reverse()
    
    # 4. Format history for Groq
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[:-1]:
        messages.append({"role": msg.role, "content": msg.content})
        
    # Current message parts
    if image_data and image_media_type:
        current_content = [
            {"type": "text", "text": content if content else "Please analyze this image."},
            {"type": "image_url", "image_url": {"url": f"data:{image_media_type};base64,{image_data}"}}
        ]
    else:
        if pdf_text:
            current_content = f"Here is the text extracted from the document the user uploaded:\n<document>\n{pdf_text}\n</document>\n\nUser message: {content}"
        elif content:
            current_content = content
        else:
            current_content = "Hello"

    messages.append({"role": "user", "content": current_content})
    
    # Use Vision model for images, otherwise default Versatile model
    current_model = VISION_MODEL_NAME if image_data else MODEL_NAME
    
    for attempt in range(2):
        try:
            if image_data:
                # Vision model doesn't support tools on Groq currently
                response = client.chat.completions.create(
                    model=current_model,
                    messages=messages,
                )
            else:
                response = client.chat.completions.create(
                    model=current_model,
                    messages=messages,
                    tools=GROQ_TOOLS,
                    tool_choice="auto",
                    parallel_tool_calls=False
                )
            
            response_message = response.choices[0].message
            
            while True:
                if response_message.tool_calls:
                    # Add assistant message with tool calls to history safely
                    assistant_msg = {
                        "role": "assistant",
                        "content": response_message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in response_message.tool_calls
                        ]
                    }
                    messages.append(assistant_msg)
                    
                    for tool_call in response_message.tool_calls:
                        tool_name = tool_call.function.name
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {}
                            
                        if tool_name == "update_user_preference":
                            key = tool_args.get("key")
                            val = tool_args.get("value")
                            prefs_dict = dict(user.preferences_json) if user.preferences_json else {}
                            if key and val:
                                prefs_dict[key] = val
                                user.preferences_json = prefs_dict
                                db.query(User).filter(User.id == user.id).update({"preferences_json": prefs_dict})
                                db.commit()
                            result = json.dumps({"status": "success", "key": key, "value": val})
                        else:
                            if tool_name in TOOLS_MAP:
                                try:
                                    result = TOOLS_MAP[tool_name](**tool_args)
                                except Exception as e:
                                    result = f"Error running tool: {str(e)}"
                            else:
                                result = f"Error: Tool {tool_name} not found."
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": str(result)
                        })
                    
                    # Call Groq again with the tool results
                    response = client.chat.completions.create(
                        model=current_model,
                        messages=messages,
                        tools=GROQ_TOOLS,
                        tool_choice="auto",
                        parallel_tool_calls=False
                    )
                    response_message = response.choices[0].message
                    continue
                
                # Check for leaked tool calls in the content
                elif response_message.content and "<function=" in response_message.content:
                    pattern = r"<function=([a-zA-Z0-9_]+)[>\(]*(.*?)[<\)]*/?function>"
                    matches = list(re.finditer(pattern, response_message.content, re.DOTALL))
                    if matches:
                        messages.append({"role": "assistant", "content": response_message.content})
                        
                        for m in matches:
                            tool_name = m.group(1)
                            tool_args_str = m.group(2)
                            try:
                                tool_args = json.loads(tool_args_str)
                            except json.JSONDecodeError:
                                tool_args = {}
                                
                            if tool_name == "update_user_preference":
                                key = tool_args.get("key")
                                val = tool_args.get("value")
                                prefs_dict = dict(user.preferences_json) if user.preferences_json else {}
                                if key and val:
                                    prefs_dict[key] = val
                                    user.preferences_json = prefs_dict
                                    db.query(User).filter(User.id == user.id).update({"preferences_json": prefs_dict})
                                    db.commit()
                                result = json.dumps({"status": "success", "key": key, "value": val})
                            else:
                                if tool_name in TOOLS_MAP:
                                    try:
                                        result = TOOLS_MAP[tool_name](**tool_args)
                                    except Exception as e:
                                        result = f"Error running tool: {str(e)}"
                                else:
                                    result = f"Error: Tool {tool_name} not found."
                            
                            # Append result as user message to feed back to the model
                            messages.append({
                                "role": "user",
                                "content": f"System Action: Tool '{tool_name}' executed. Result: {result}"
                            })
                            
                        response = client.chat.completions.create(
                            model=current_model,
                            messages=messages,
                            tools=GROQ_TOOLS,
                            tool_choice="auto",
                            parallel_tool_calls=False
                        )
                        response_message = response.choices[0].message
                        continue
                        
                # No more tools to call
                break
                
            final_text = response_message.content
            
            # 5. Clean up any lingering raw function tags before showing to user
            if final_text:
                final_text = re.sub(r"<function=.*?</function>", "", final_text, flags=re.DOTALL)
                final_text = final_text.strip()
            
            # 5. Save Assistant response
            asst_msg = Message(user_id=user.id, role="assistant", content=final_text)
            db.add(asst_msg)
            db.commit()
            
            return final_text
    
        except Exception as e:
            if "429" in str(e) and attempt == 0:
                print("Rate limit (429) hit. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            traceback.print_exc()
            return f"I couldn't verify that right now. Error: {str(e)}"

