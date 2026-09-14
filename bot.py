import os
import re
import time
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
    
    for attempt in range(3):
        res = requests.post(url, headers=headers, json=payload, timeout=35)
        if res.status_code == 200:
            res_json = res.json()
            return res_json['candidates'][0]['content']['parts'][0]['text']
        elif res.status_code == 429:
            time.sleep(4 * (attempt + 1))
        else:
            res_json = res.json()
            raise Exception(f"Gemini API Error {res.status_code}: {res_json}")
            
    raise Exception("429_LIMIT")

def extract_search_term_python(user_text):
    marka_match = re.search(r'Marka:\s*([^\n]+)', user_text, re.IGNORECASE)
    model_match = re.search(r'Model:\s*([^\n]+)', user_text, re.IGNORECASE)
    
    marka = marka_match.group(1).strip() if marka_match else ""
    model = model_match.group(1).strip() if model_match else ""
    
    ignore_words = ["fərq etmir", "ferq etmir", "fark etmez", "любая", "любой"]
    
    term_parts = []
    if marka and not any(w in marka.lower() for w in ignore_words):
        term_parts.append(marka)
    if model and not any(w in model.lower() for w in ignore_words):
        term_parts.append(model)
        
    if term_parts:
        return " ".join(term_parts)
        
    return "sedan"

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
                
                listings.append(
                    f"ELAN:\n"
                    f"- Adı: {title}\n"
                    f"- Qiyməti: {price}\n"
                    f"- Göstəricilər: {attrs}\n"
                    f"- BİRBAŞA LINK: {full_url}"
                )
                
        return "\n\n".join(listings) if listings else f"Axtarış keçidi: {search_url}"
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

        Turbo.az-dan tapılan real elanların siyahısı:
        {raw_cars}

        Mütləq qaydalar:
        1. Yuxarıdakı siyahıdan müştərinin büdcəsinə və tələblərinə ən uyğun variantları seç.
        2. Cavabı Azərbaycan dilində peşəkar avto-broker üslubunda tərtib et.
        3. HƏR BİR VARIANT ÜÇÜN MÜTLƏQ aşağıdakı formatda yaz:
           - Avtomobilin adı və ili
           - Qiyməti
           - Büdcəyə uyğunluq şərhiniz
           - BİRBAŞA ELAN LİNKİ: Siyahıda "BİRBAŞA LINK:" qarşısında yazılan https://turbo.az/autos/... URL-ni EYNİLƏ DƏQİQ OLARAQ MƏTNƏ ƏLAVƏ ET.
        """
        final_analysis = ask_gemini(ai_prompt)
        
        await update.message.reply_text(final_analysis, disable_web_page_preview=False)
    except Exception as e:
        if str(e) == "429_LIMIT":
            await update.message.reply_text("⚠️ Serverdə yüksək yüklənmə var. Zəhmət olmasa 10-15 saniyə sonra yenidən cəhd edin.")
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
