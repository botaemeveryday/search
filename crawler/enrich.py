"""
crawler/enrich.py
Добавляет keywords к документам через DeepSeek API.
Запускается только при индексации, не в рантайме.
"""

import os
import json
import time
import hashlib
from pathlib import Path
import requests

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CACHE_DIR        = Path(".cache/enrich")

API_URL = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = """Ты помогаешь индексировать учебные материалы по CS.
Для каждого документа верни JSON с полем "keywords" — массив строк.
Включи:
- синонимы заголовка (рус + eng)
- аббревиатуры (CFS, RB-tree, БД, ОС...)
- альтернативные написания (лаба, лабораторная, lab, л/р)
- номера если есть (4.03, 4_03, 403)
- ключевые термины из текста (не более 20)
Только JSON, без пояснений."""


def enrich_doc(doc: dict) -> list[str]:
    """Возвращает список keywords для документа."""
    cache_key  = hashlib.md5(doc["url"].encode()).hexdigest()
    cache_path = CACHE_DIR / f"{cache_key}.json"

    if cache_path.exists():
        return json.loads(cache_path.read_text())

    if not DEEPSEEK_API_KEY:
        return []

    prompt = f"Заголовок: {doc['title']}\n\nФрагмент текста:\n{doc['content'][:1500]}"

    try:
        r = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system",  "content": SYSTEM_PROMPT},
                    {"role": "user",    "content": prompt},
                ],
                "max_tokens": 200,
                "temperature": 0.2,
            },
            timeout=20,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()

        # Убираем возможные ```json ``` обёртки
        text = text.replace("```json", "").replace("```", "").strip()
        keywords = json.loads(text).get("keywords", [])

    except Exception as e:
        print(f"  enrich error ({doc['title'][:40]}): {e}")
        keywords = []

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(keywords, ensure_ascii=False))
    time.sleep(0.3)  # rate limit
    return keywords


def enrich_all(docs: list[dict]) -> list[dict]:
    print(f"[enrich] обогащаем {len(docs)} документов...")
    for i, doc in enumerate(docs):
        keywords = enrich_doc(doc)
        if keywords:
            doc["keywords"] = keywords
            # Добавляем keywords в content чтобы Pagefind их индексировал
            doc["content"] = doc["content"] + "\n\nкейворды: " + " ".join(keywords)
        if i % 100 == 0:
            print(f"  [{i}/{len(docs)}]")
    print("[enrich] готово")
    return docs
