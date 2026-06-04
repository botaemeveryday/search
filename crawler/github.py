"""
crawler/github.py
Индексирует GitHub-репозитории по темам CS ИТМО.
Выдаёт список документов для index.json.
"""

import os
import time
import json
import base64
import hashlib
import requests
from pathlib import Path

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
CACHE_DIR    = Path(".cache/github")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

# Темы для поиска
TOPICS = [
    "itmo операционные системы конспект",
    "itmo базы данных конспект",
    "itmo алгоритмы конспект",
    "itmo cpp конспект",
    "itmo java конспект",
    "itmo математика конспект",
    "физика лабораторная работа решение",
    "cs notes итмо",
]

# Расширения файлов которые индексируем
ALLOWED_EXT = {".md", ".txt", ".rst"}

# Файлы которые пропускаем
SKIP_FILES = {"readme.md", "license.md", "contributing.md", "changelog.md"}


def search_repos(query: str, max_repos: int = 10) -> list[dict]:
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "per_page": max_repos}
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("items", [])


def get_repo_tree(owner: str, repo: str, branch: str = "HEAD") -> list[dict]:
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}"
    r = requests.get(url, headers=HEADERS, params={"recursive": "1"}, timeout=15)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return r.json().get("tree", [])


def get_file_content(owner: str, repo: str, path: str) -> str | None:
    cache_key = hashlib.md5(f"{owner}/{repo}/{path}".encode()).hexdigest()
    cache_path = CACHE_DIR / f"{cache_key}.txt"

    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="ignore")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        return None

    data = r.json()
    if data.get("encoding") != "base64" or not data.get("content"):
        return None

    try:
        content = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(content, encoding="utf-8")
    return content


def crawl(max_repos_per_query: int = 5) -> list[dict]:
    docs = []
    seen_repos = set()

    for query in TOPICS:
        print(f"[github] поиск: {query}")
        try:
            repos = search_repos(query, max_repos_per_query)
        except Exception as e:
            print(f"  ошибка поиска: {e}")
            continue

        for repo_info in repos:
            full_name = repo_info["full_name"]
            if full_name in seen_repos:
                continue
            seen_repos.add(full_name)

            owner, repo = full_name.split("/")
            stars       = repo_info.get("stargazers_count", 0)
            description = repo_info.get("description") or ""
            html_url    = repo_info["html_url"]
            default_br  = repo_info.get("default_branch", "main")

            print(f"  репо: {full_name} ★{stars}")

            try:
                tree = get_repo_tree(owner, repo, default_br)
            except Exception as e:
                print(f"    ошибка дерева: {e}")
                continue

            md_files = [
                f for f in tree
                if f["type"] == "blob"
                and Path(f["path"]).suffix.lower() in ALLOWED_EXT
                and Path(f["path"]).name.lower() not in SKIP_FILES
                and f.get("size", 0) < 200_000  # пропускаем >200kb
            ]

            # Максимум 30 файлов из одного репо
            for file_info in md_files[:30]:
                path     = file_info["path"]
                file_url = f"{html_url}/blob/{default_br}/{path}"

                content = get_file_content(owner, repo, path)
                if not content or len(content.strip()) < 100:
                    continue

                # Заголовок — первый H1 или имя файла
                title = ""
                for line in content.splitlines()[:20]:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                if not title:
                    title = Path(path).stem.replace("-", " ").replace("_", " ")

                # Сниппет — первые 300 символов без markdown-разметки
                import re
                clean = re.sub(r"[#*`\[\]>]", "", content[:600]).strip()
                snippet = clean[:300].replace("\n", " ").strip()

                docs.append({
                    "url":     file_url,
                    "title":   title,
                    "content": content[:8000],  # обрезаем для индекса
                    "snippet": snippet,
                    "source":  "github",
                    "meta": {
                        "repo":        full_name,
                        "stars":       stars,
                        "description": description[:200],
                        "path":        path,
                    }
                })

            time.sleep(0.5)  # уважаем rate limit

    print(f"[github] итого документов: {len(docs)}")
    return docs


if __name__ == "__main__":
    docs = crawl()
    print(json.dumps(docs[:2], ensure_ascii=False, indent=2))
