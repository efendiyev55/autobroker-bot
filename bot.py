import os
import threading
from flask import Flask
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Auto Broker Bot Status: Active"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

# Берем API-ключ из секретных настроек Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Обновленный токен бота
TELEGRAM_BOT_TOKEN = "8699795204:AAHu2uUhZqRMNuHtP4Yc4NotSeDJSvHrdYI"

def ask_gemini(prompt_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}]
    }
    res = requests.post(url, headers=headers, json=payload, timeout=20)
    res_json = res.json()
    if res.status_code == 200:
        return res_json['candidates'][0]['content']['parts'][0]['text']
    else:
        raise Exception(f"Gemini API Error {res.status_code}: {res_json}")

def search_turbo(query_text):
    search_url = f"https://turbo.az/autos?q[full_text]={requests.utils.quote(query_text)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        listings = []
        for item in soup.select('.products-i')[:15]:
            title = item.select_one('.products-i__name')
            price = item.select_one('.product-price')
            link = item.select_one('a')
            if title and price and link:
                listings.append(f"{title.text.strip()} | {price.text.strip()} | https://turbo.az{link['href']}")
                
        return "\n".join(listings)
    except Exception as e:
        return f"Ошибка парсинга: {e}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("🔍 Ищу варианты на Turbo.az...")

    try:
        parse_prompt = f"Извлеки только марку и модель авто на английском из текста: {user_text}"
        search_query = ask_gemini(parse_prompt).strip()
        
        raw_cars = search_turbo(search_query)

        if not raw_cars or "Ошибка" in raw_cars:
            await update.message.reply_text("Не удалось получить предложения с Turbo.az.")
            return

        ai_prompt = f"Запрос клиента: {user_text}\nНайденные варианты: {raw_cars}\nВыбери 3 самых выгодных. Выведи: Название, Цена, Почему выгодно, Ссылка."
        final_analysis = ask_gemini(ai_prompt)
        await update.message.reply_text(final_analysis)
    except Exception as e:
        await update.message.reply_text(f"Техническая ошибка: {e}")

def main():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
