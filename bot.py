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
    
    # Имитируем реальный браузер с мобильного устройства, чтобы обходить 403 ошибку
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'az-AZ,az;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code != 200:
            # Если сайт всё же заблокировал, возвращаем прямую рабочую ссылку на результаты поиска на самом сайте
            return f"Прямая ссылка на поиск: {search_url}"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        listings = []
        items = soup.select('.products-i')
        
        for item in items[:5]:
            title = item.select_one('.products-i__name')
            price = item.select_one('.product-price')
            link = item.select_one('a')
            if title and link:
                price_text = price.text.strip() if price else ""
                listings.append(f"- {title.text.strip()} ({price_text}) | https://turbo.az{link['href']}")
                
        return "\n".join(listings) if listings else f"Прямая ссылка на поиск: {search_url}"
    except Exception as e:
        return f"Прямая ссылка на поиск: {search_url}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("🔍 Turbo.az-dən uyğun variantlar axtarılır...")

    try:
        parse_prompt = f"İstifadəçi sorğusundan yalnız avtomobil markasını (məsələn: Changan, Toyota) çıxar. Əgər yoxdursa 'Changan' yaz: {user_text}"
        search_query = ask_gemini(parse_prompt).strip()
        
        raw_cars = search_turbo(search_query)

        ai_prompt = f"""
        Müştərinin sorğusu (Azərbaycan dilində cavab ver):
        {user_text}

        Saytdan tapılan məlumatlar / Axtarış linki:
        {raw_cars}

        Tapşırıq: Müştəriyə onun büdcəsinə (19.000 AZN) və tələblərinə uyğun 3ən yaxşı variantı təqdim et. 
        Hər bir model üçün adını, təxmini qiymətini, niyə uyğun olduğunu və əgər link varsa birbaşa qeyd et. 
        Üslub peşəkar avto-broker kimi olsun.
        """
        final_analysis = ask_gemini(ai_prompt)
        await update.message.reply_text(final_analysis)
    except Exception as e:
        await update.message.reply_text(f"Texniki xəta baş verdi: {e}")

def main():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.app_add_handler = app.add_handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
