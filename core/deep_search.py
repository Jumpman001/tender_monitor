import asyncio
import aiohttp
import ssl
import certifi
from bs4 import BeautifulSoup
import google.generativeai as genai
import os
from config import GEMINI_API_KEY
from utils.logger import logger

genai.configure(api_key=GEMINI_API_KEY)

async def ddg_search(query: str, max_results: int = 7) -> list[str]:
    """Скрейпинг HTML версии DuckDuckGo для поиска информации о проекте."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    }
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://html.duckduckgo.com/html/', 
                data={'q': query}, 
                headers=headers, 
                ssl=ssl_ctx,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status == 200:
                    html = await r.text()
                    soup = BeautifulSoup(html, 'lxml')
                    for a in soup.select('.result__snippet')[:max_results]:
                        text = a.get_text(strip=True)
                        if text:
                            results.append(text)
    except Exception as e:
        logger.error("[DeepSearch] Ошибка поиска DuckDuckGo: %s", e)
        
    return results

async def deep_investigate(project_name: str) -> str:
    """Выполняет поиск в интернете и генерирует отчет через Gemini."""
    logger.info("[DeepSearch] Ищем в сети: %s", project_name)
    
    # Расширяем запрос для лучшего поиска
    query = f"{project_name} (Tajikistan OR water OR tender OR procurement OR project)"
    snippets = await ddg_search(query)
    
    if not snippets:
        return "К сожалению, не удалось найти информацию об этом проекте в открытых источниках интернета."
        
    context = "\n\n".join([f"- {s}" for s in snippets])
    
    prompt = f"""
Ты — профессиональный аналитик тендеров и инфраструктурных проектов.
Пользователь запросил глубокий поиск по проекту: "{project_name}".

Я выполнил поиск в интернете и собрал следующие фрагменты (snippets) из открытых источников:
{context}

Твоя задача — составить максимально подробное, структурированное и понятное резюме (досье) по этому проекту на основе предоставленных фрагментов.
Если фрагменты не относятся к запрошенному проекту, честно скажи, что точной информации найти не удалось, но укажи, что удалось найти.

Формат ответа (используй строго HTML теги для Telegram: <b>жирный</b>, <i>курсив</i>, <u>подчеркнутый</u>, <s>зачеркнутый</s>, <a href="URL">ссылка</a>. Не используй Markdown со звездочками **!):
🔍 <b>Досье проекта: [Название из фрагментов или запроса]</b>

📝 <b>Краткое описание</b>
[О чем проект, какие цели преследует]

🏦 <b>Финансирование и доноры</b>
[Кто спонсирует, бюджет, если упоминается]

🏗 <b>Текущий статус и детали</b>
[На какой стадии, какие работы планируются, какие дедлайны]

📞 <b>Контакты и организации</b>
[Связанные организации (например Dushanbe Vodokanal), министерства, контакты]

Используй эмодзи и делай текст удобным для чтения с телефона. Пиши на русском языке.
Не придумывай информацию, используй только то, что есть во фрагментах.
"""

    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: model.generate_content(prompt, request_options={"timeout": 30})
        )
        return response.text.replace("**", "") # На всякий случай чистим маркдаун
    except Exception as e:
        logger.error("[DeepSearch] Ошибка генерации Gemini: %s", e)
        return "⚠️ Произошла ошибка при анализе данных нейросетью. Попробуйте чуть позже."
