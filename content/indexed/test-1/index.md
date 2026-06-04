---
title: "Планировщик процессов Linux — Лекция 7"
url_original: "https://botaemeveryday.github.io/notes/posts/operation-systems/lecture-7/"
source: "notes"
tags: ["notes", "ОС"]
keywords: ["планировщик", "CFS", "Linux", "scheduler", "процесс", "ядро"]
snippet: "CFS — Completely Fair Scheduler. Красно-чёрное дерево, O(log n)."
draft: true
layout: "indexed"
---

CFS — Completely Fair Scheduler. Каждый процесс получает CPU пропорционально весу.
Реализован через красно-чёрное дерево. Временная сложность O(log n).
Планировщик Linux минимизирует время простоя процессора.