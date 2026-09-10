import os
import json
import logging
from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError
from openai import OpenAI

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# এনভায়রনমেন্ট ভেরিয়েবল
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

# DeepSeek ক্লায়েন্ট (OpenAI SDK সামঞ্জস্যপূর্ণ)
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)


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
    """DeepSeek API থেকে উত্তর পাওয়া"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Reply in the same language as the user's message."
                },
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        return "দুঃখিত, এখন উত্তর দিতে পারছি না। পরে আবার চেষ্টা করুন।"


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function Handler"""

    def do_POST(self):
        """টেলিগ্রাম থেকে আসা মেসেজ হ্যান্ডেল করা"""

        # সিক্রেট ভেরিফিকেশন
        if TELEGRAM_WEBHOOK_SECRET:
            query = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
            if params.get("secret") != TELEGRAM_WEBHOOK_SECRET:
                logger.warning("Invalid webhook secret")
                self.send_response(403)
                self.end_headers()
                return

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
                reply = get_ai_response(text)
            else:
                reply = "দুঃখিত, আমি শুধু টেক্সট মেসেজ বুঝতে পারি।"

            # উত্তর পাঠানো
            send_telegram_message(chat_id, reply)

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
            self.send_response(200)
            self.end_headers()

    def do_GET(self):
        """হেলথ চেক"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Telegram Bot is running with DeepSeek!")
