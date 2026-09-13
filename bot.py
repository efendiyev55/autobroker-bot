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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = "8699795204:AAHu2uUhZqRMNuHtP4Yc4NotSeDJSvHrdYI"

def ask_gemini(prompt_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
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
    
    # Расширенные заголовки под видом реального Safari/Chrome с мобильного/ПК
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://turbo.az/',
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code != 200:
            return f"Ошибка сайта: статус {response.status_code}"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        listings = []
        # Проверяем разные варианты классов карточек на Turbo.az
        items = soup.select('.products-i') or soup.select('.product') or soup.select('[class*="products-i"]')
        
        for item in items[:20]:
            title = item.select_one('.products-i__name') or item.select_one('[class*="name"]')
            price = item.select_one('.product-price') or item.select_one('[class*="price"]')
            link = item.select_one('a')
            if title and link:
                price_text = price.text.strip() if price else "Цена не указана"
                href = link['href']
                full_link = f"https://turbo.az{href}" if href.startswith('/') else href
                listings.append(f"{title.text.strip()} | {price_text} | {full_link}")
                
        return "\n".join(listings) if listings else ""
    except Exception as e:
        return f"Ошибка парсинга: {e}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("🔍 Ищу варианты на Turbo.az...")

    try:
        # Достаем ключевые слова для поиска (например, марку или общий класс)
        parse_prompt = f"Извлеки из текста только марку автомобиля (например, Changan, Toyota, Kia). Если марки нет, напиши 'sedan': {user_text}"
        search_query = ask_gemini(parse_prompt).strip()
        if len(search_query) < 2:
            search_query = "sedan"

        raw_cars = search_turbo(search_query)

        # Если по марке не нашлось, пробуем общий запрос по сайту
        if not raw_cars:
            raw_cars = search_turbo("mashin")

        if not raw_cars:
            await update.message.reply_text("Не удалось получить данные с Turbo.az (сайт защищается от запросов). Попробуй отправить запрос еще раз через пару минут.")
            return

        ai_prompt = f"""
        Анкета клиента:
        {user_text}

        Найденные объявления на сайте:
        {raw_cars}

        Задача: Выбери до 3 лучших вариантов, которые ближе всего подходят по параметрам (бюджет до 19000 AZN, гибрид/седан если есть). 
        Выведи для каждого: Название, Цена, Почему подходит, Ссылка.
        """
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
