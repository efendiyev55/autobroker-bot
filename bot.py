import os
import re
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
    # Возвращена рабочая модель gemini-3.6-flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}]
    }
    res = requests.post(url, headers=headers, json=payload, timeout=35)
    res_json = res.json()
    if res.status_code == 200:
        return res_json['candidates'][0]['content']['parts'][0]['text']
    elif res.status_code == 429:
        raise Exception("429_LIMIT")
    else:
        raise Exception(f"Gemini API Error {res.status_code}: {res_json}")

def extract_search_term_python(user_text):
    """Вытаскивает марку и модель из текста без запроса к AI (экономит 50% лимитов)"""
    marka = re.search(r'Marka:\s*([^\n]+)', user_text, re.IGNORECASE)
    model = re.search(r'Model:\s*([^\n]+)', user_text, re.IGNORECASE)
    
    term = ""
    if marka:
        term += marka.group(1).strip() + " "
    if model:
        term += model.group(1).strip()
        
    if term.strip():
        return term.strip()
        
    clean_text = re.sub(r'[^\w\s]', '', user_text)
    words = [w for w in clean_text.split() if len(w) > 2]
    return " ".join(words[:2]) if words else "Changan"

def search_turbo(query_text):
    search_url = f"https://turbo.az/autos?q[full_text]={requests.utils.quote(query_text)}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'az-AZ,az;q=0.9,en;q=0.8',
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=12)
        if response.status_code != 200:
            return f"Axtarış keçidi: {search_url}"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        listings = []
        items = soup.select('.products-i')
        
        for item in items[:6]:
            link_tag = item.select_one('a.products-i__link') or item.select_one('a')
            title_tag = item.select_one('.products-i__name')
            price_tag = item.select_one('.product-price') or item.select_one('.products-i__price')
            attr_tag = item.select_one('.products-i__attributes')
            
            if link_tag and link_tag.get('href'):
                href = link_tag['href']
                full_url = f"https://turbo.az{href}" if href.startswith('/') else href
                title = title_tag.text.strip() if title_tag else "Avtomobil"
                price = price_tag.text.strip() if price_tag else "Qiymət qeyd olunmayıb"
                attrs = attr_tag.text.strip() if attr_tag else ""
                
                listings.append(f"Model: {title} | Qiymət: {price} | Göstəricilər: {attrs} | Keçid: {full_url}")
                
        return "\n".join(listings) if listings else f"Axtarış keçidi: {search_url}"
    except Exception:
        return f"Axtarış keçidi: {search_url}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("🔍 Turbo.az-dan ən yaxşı elanlar toplanılır və təhlil edilir...")

    try:
        search_query = extract_search_term_python(user_text)
        raw_cars = search_turbo(search_query)

        ai_prompt = f"""
        Müştərinin sorğusu:
        {user_text}

        Saytdan tapılan real elanların siyahısı:
        {raw_cars}

        Tapşırıq:
        1. Müştərinin büdcəsinə, ilkin ödənişinə və tələblərinə uyğun olaraq yuxarıdakı siyahıdan ən yaxşı variantları seç.
        2. Cavabı Azərbaycan dilində peşəkar avto-broker üslubunda tərtib et.
        3. HƏR BİR VARIANT ÜÇÜN MÜTLƏQ:
           - Avtomobilin adını və ilini
           - Qiymətini
           - Kredit/lizinq və ya büdcəyə uyğunluq şərhini
           - Siyahıda verilən DƏQİQ BİRBAŞA ELAN LİNKİNİ (Keçid) göster.
        """
        final_analysis = ask_gemini(ai_prompt)
        await update.message.reply_text(final_analysis, disable_web_page_preview=False)
    except Exception as e:
        if str(e) == "429_LIMIT":
            await update.message.reply_text("⚠️ Sistemdə çoxlu sorğu var. Zəhmət olmasa 30 saniyə sonra yenidən cəhd edin.")
        else:
            await update.message.reply_text(f"Texniki xəta baş verdi: {e}")

def main():
    t = threading.Thread(target=run_web)
    t.daemon = True
    t.start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
