import os
import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError
import openai

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# এনভায়রনমেন্ট ভেরিয়েবল
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

# OpenAI ক্লায়েন্ট
openai.api_key = OPENAI_API_KEY


def send_telegram_message(chat_id: int, text: str) -> bool:
    """টেলিগ্রামে মেসেজ পাঠানো"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text[:4096]  # টেলিগ্রামের মেসেজ লিমিট
    }).encode("utf-8")
    
    try:
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=25) as response:
            return response.status == 200
    except URLError as e:
        logger.error(f"Telegram API error: {e}")
        return False


def get_ai_response(user_message: str) -> str:
    """OpenAI থেকে উত্তর পাওয়া"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # খরচ কমাতে mini মডেল
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Reply in the same language as the user's message."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "দুঃখিত, এখন উত্তর দিতে পারছি না। পরে আবার চেষ্টা করুন।"


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function Handler"""
    
    def do_POST(self):
        """টেলিগ্রাম থেকে আসা মেসেজ হ্যান্ডেল করা"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        
        try:
            update = json.loads(body.decode("utf-8"))
            logger.info(f"Received update: {json.dumps(update)[:500]}")
            
            # মেসেজ আছে কিনা চেক করা
            if "message" not in update:
                self.send_response(200)
                self.end_headers()
                return
            
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "")
            
            # কমান্ড হ্যান্ডলিং
            if text == "/start":
                reply = "হ্যালো! আমি একটি AI সহায়ক বট। আমাকে যেকোনো প্রশ্ন করুন, আমি উত্তর দেওয়ার চেষ্টা করব।"
            elif text.startswith("/"):
                reply = "দুঃখিত, এই কমান্ডটি এখনো সাপোর্ট করা হয়নি।"
            elif text:
                # AI থেকে উত্তর পাওয়া
                reply = get_ai_response(text)
            else:
                reply = "দুঃখিত, আমি শুধু টেক্সট মেসেজ বুঝতে পারি।"
            
            # উত্তর পাঠানো
            send_telegram_message(chat_id, reply)
            
            # সফল রেসপন্স
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            self.send_response(400)
            self.end_headers()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.send_response(200)  # টেলিগ্রামকে 200 পাঠানো যাতে রিট্রাই না করে
            self.end_headers()
    
    def do_GET(self):
        """হেলথ চেক"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Telegram Bot is running!")
