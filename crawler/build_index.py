"""
crawler/build_index.py
Точка входа: собирает все источники, обогащает, генерирует HTML-страницы
которые Pagefind потом проиндексирует.
"""

import json
import shutil
from pathlib import Path

from github import crawl as crawl_github
from neerc   import crawl as crawl_neerc
from enrich  import enrich_all

OUTPUT_DIR = Path("content/indexed")


def source_to_tags(doc: dict) -> list[str]:
    tags = [doc["source"]]
    meta = doc.get("meta", {})
    if meta.get("repo"):
        tags.append("github")
    return tags


def write_hugo_page(doc: dict, idx: int) -> None:
    """Пишем каждый документ как Hugo-страницу — Pagefind их проиндексирует."""
    slug     = f"doc-{idx:06d}"
    out_dir  = OUTPUT_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    tags     = source_to_tags(doc)
    keywords = doc.get("keywords", [])
    meta     = doc.get("meta", {})

    # Front matter
    front = {
        "title":       doc["title"],
        "url_original": doc["url"],
        "source":      doc["source"],
        "tags":        tags,
        "keywords":    keywords,
        "snippet":     doc.get("snippet", "")[:300],
        "draft":       False,
        "layout":      "indexed",
    }
    if meta.get("repo"):
        front["repo"]  = meta["repo"]
        front["stars"] = meta.get("stars", 0)

    # Пишем index.md
    content_text = doc.get("content", "")
    md = "---\n" + json.dumps(front, ensure_ascii=False, indent=2)[1:-1].strip() + "\n---\n\n" + content_text

    (out_dir / "index.md").write_text(md, encoding="utf-8")


def main():
    print("=" * 50)
    print("Сборка поискового индекса")
    print("=" * 50)

    # Очищаем старый контент
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # Собираем источники
    docs = []
    docs += crawl_github()
    docs += crawl_neerc()

    print(f"\nВсего документов до обогащения: {len(docs)}")

    # Обогащаем keywords
    docs = enrich_all(docs)

    # Пишем Hugo-страницы
    for i, doc in enumerate(docs):
        write_hugo_page(doc, i)

    print(f"\nГотово. Написано страниц: {len(docs)}")
    print("Запусти: hugo && npx pagefind --site public")


if __name__ == "__main__":
    main()
