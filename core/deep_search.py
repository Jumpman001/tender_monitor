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
    
    # Строго ограничиваем поиск нашей тематикой
    query = f"{project_name} Tajikistan (water OR pipe OR irrigation OR sanitation OR sewer OR трубы OR водоснабжение)"
    snippets = await ddg_search(query)
    
    if not snippets:
        return "К сожалению, не удалось найти информацию об этом проекте в открытых источниках интернета."
        
    context = "\n\n".join([f"- {s}" for s in snippets])
    
    prompt = f"""
Ты — строгий аналитик тендеров и инфраструктурных проектов. Наша компания занимается поставками труб (DN >= 400мм) для систем водоснабжения, канализации и ирригации в Таджикистане.

Пользователь запросил поиск по: "{project_name}".
Я нашел следующие фрагменты в сети:
{context}

ВНИМАНИЕ! Сначала проверь:
Относится ли найденная информация к проектам по: водоснабжению, водоотведению, канализации, ирригации или замене/прокладке труб?
Если информация НИКАК не связана с трубами или водой (например, это строительство школ, закупка ИТ-оборудования, медицина или случайные новости), СРАЗУ отвечай так и БОЛЬШЕ НИЧЕГО НЕ ПИШИ:
"🚫 <b>Нецелевой проект</b>\nНайденная информация не относится к проектам водоснабжения, канализации или ирригации."

Если проект ЦЕЛЕВОЙ (вода, трубы, канализация, ирригация), составь подробное досье:
Формат ответа (строго HTML: <b>жирный</b>, <i>курсив</i>. Не используй Markdown **):
🔍 <b>Досье проекта: [Название]</b>

📝 <b>Краткое описание</b>
[О чем проект]

🏦 <b>Финансирование и доноры</b>
[Кто спонсирует, бюджет]

🏗 <b>Текущий статус и детали</b>
[На какой стадии, планируемые работы с трубами]

📞 <b>Контакты и организации</b>
[Связанные организации, контакты]

Используй только факты из фрагментов! Пиши на русском.
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
