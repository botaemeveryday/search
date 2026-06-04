"""
crawler/neerc.py
Парсит NEERC IFMO wiki (e-olymp / neerc.ifmo.ru).
"""

import re
import time
import json
import hashlib
import requests
from pathlib import Path
from html.parser import HTMLParser

BASE_URL  = "https://neerc.ifmo.ru/wiki"
INDEX_URL = f"{BASE_URL}/index.php/Special:AllPages"
CACHE_DIR = Path(".cache/neerc")

HEADERS = {
    "User-Agent": "botaemeveryday-search-indexer/1.0 (https://github.com/botaemeveryday/search)",
}

# Категории которые индексируем
TARGET_PREFIXES = [
    "Алгоритм", "Структура", "Граф", "Сортировка", "Дерево",
    "Динамическое", "Жадный", "Задача", "Матрица", "Строк",
    "Планировщик", "Процесс", "Память", "Файловая", "Сеть",
]


class WikiTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_content = False
        self.depth      = 0
        self.text_parts = []
        self._skip      = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        idd = attrs_dict.get("id", "")

        if idd == "mw-content-text" or "mw-parser-output" in cls:
            self.in_content = True
            self.depth = 0

        if self.in_content:
            self.depth += 1
            # пропускаем навигацию, TOC, сноски
            if tag in ("table", "div") and any(
                x in cls for x in ["toc", "navbox", "reflist", "noprint"]
            ):
                self._skip = True

    def handle_endtag(self, tag):
        if self.in_content:
            self.depth -= 1
            if self.depth <= 0:
                self.in_content = False
            if tag in ("table", "div"):
                self._skip = False

    def handle_data(self, data):
        if self.in_content and not self._skip:
            stripped = data.strip()
            if stripped:
                self.text_parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


def fetch(url: str) -> str | None:
    cache_key  = hashlib.md5(url.encode()).hexdigest()
    cache_path = CACHE_DIR / f"{cache_key}.html"

    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="ignore")

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  fetch error {url}: {e}")
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(r.text, encoding="utf-8")
    time.sleep(1)  # вежливая пауза
    return r.text


def get_all_page_titles() -> list[str]:
    """Получаем список всех страниц через Special:AllPages."""
    titles = []
    url    = INDEX_URL

    while url:
        html = fetch(url)
        if not html:
            break

        # Ищем ссылки на страницы
        links = re.findall(r'href="/wiki/index\.php/([^"?#]+)"', html)
        for link in links:
            title = requests.utils.unquote(link).replace("_", " ")
            if any(title.startswith(p) for p in TARGET_PREFIXES):
                titles.append(title)

        # Следующая страница пагинации
        next_match = re.search(r'href="(/wiki/index\.php\?[^"]*from=[^"]+)"[^>]*>Следующая', html)
        if next_match:
            url = f"https://neerc.ifmo.ru{next_match.group(1)}"
        else:
            break

    return list(set(titles))


def parse_page(title: str) -> dict | None:
    slug = title.replace(" ", "_")
    url  = f"{BASE_URL}/index.php/{requests.utils.quote(slug)}"
    html = fetch(url)
    if not html:
        return None

    # Парсим текст
    parser = WikiTextParser()
    parser.feed(html)
    text = parser.get_text()

    if len(text.strip()) < 100:
        return None

    snippet = text[:300].strip()

    return {
        "url":     url,
        "title":   title,
        "content": text[:8000],
        "snippet": snippet,
        "source":  "neerc",
        "meta":    {},
    }


def crawl() -> list[dict]:
    print("[neerc] получаем список страниц...")
    titles = get_all_page_titles()
    print(f"[neerc] найдено страниц: {len(titles)}")

    docs = []
    for i, title in enumerate(titles):
        doc = parse_page(title)
        if doc:
            docs.append(doc)
        if i % 50 == 0:
            print(f"  [{i}/{len(titles)}] {title}")

    print(f"[neerc] итого документов: {len(docs)}")
    return docs


if __name__ == "__main__":
    docs = crawl()
    print(json.dumps(docs[:2], ensure_ascii=False, indent=2))
