(function () {
  'use strict';

  // ── Тема ────────────────────────────────────────────────────
  function getTheme() { return localStorage.getItem('theme') || 'light'; }
  function setTheme(t) {
    document.documentElement.className = t;
    localStorage.setItem('theme', t);
  }
  function toggleTheme() { setTheme(getTheme() === 'dark' ? 'light' : 'dark'); }

  document.querySelectorAll('.theme-toggle').forEach(function (btn) {
    btn.addEventListener('click', toggleTheme);
  });

  // ── Нормализация запроса ─────────────────────────────────────
  // "физика лаба 4.03" → ["физика", "лаба", "лаб", "4.03", "4_03", "403"]
  function normalizeQuery(q) {
    const base = q.trim().toLowerCase();

    // заменяем _ и . на пробел для токенизации
    const tokens = base.split(/[\s_.\-\/]+/).filter(Boolean);

    const expanded = new Set(tokens);

    tokens.forEach(function (t) {
      // "лаба" → "лабораторная", "лаб"
      if (/^лаб/.test(t)) { expanded.add('лаб'); expanded.add('лабораторная'); }
      // "4.03" и "4_03" — добавляем оба варианта
      if (/^\d+[._]\d+$/.test(t)) {
        expanded.add(t.replace(/[._]/, '.'));
        expanded.add(t.replace(/[._]/, '_'));
        expanded.add(t.replace(/[._]/, ''));
      }
      // "конспект" / "конспекты"
      if (t === 'конспект' || t === 'конспекты') { expanded.add('конспект'); }
    });

    return Array.from(expanded).join(' ');
  }

  // ── URL-стейт ────────────────────────────────────────────────
  function getQueryParam(name) {
    return new URLSearchParams(window.location.search).get(name) || '';
  }
  function setQueryParam(name, value) {
    const url = new URL(window.location.href);
    if (value) { url.searchParams.set(name, value); }
    else        { url.searchParams.delete(name); }
    history.pushState({}, '', url.toString());
  }

  // ── DOM-элементы ─────────────────────────────────────────────
  const homePage     = document.querySelector('.home');
  const resultsPage  = document.getElementById('resultsPage');
  const searchInput  = document.getElementById('searchInput');
  const searchClear  = document.getElementById('searchClear');
  const btnSearch    = document.getElementById('btnSearch');
  const btnLucky     = document.getElementById('btnLucky');

  const searchInputR = document.getElementById('searchInputResults');
  const searchClearR = document.getElementById('searchClearResults');
  const resultsList  = document.getElementById('resultsList');
  const resultsMeta  = document.getElementById('resultsMeta');
  const resultsPag   = document.getElementById('resultsPagination');
  const filtersEl    = document.getElementById('resultsFilters');

  // ── Переход главная ↔ результаты ────────────────────────────
  function showResults() {
    if (!homePage || !resultsPage) return;
    homePage.classList.add('hidden');
    resultsPage.classList.remove('hidden');
  }
  function showHome() {
    if (!homePage || !resultsPage) return;
    resultsPage.classList.add('hidden');
    homePage.classList.remove('hidden');
  }

  // ── Кнопка очистить ──────────────────────────────────────────
  function bindClear(input, clearBtn) {
    if (!input || !clearBtn) return;
    input.addEventListener('input', function () {
      clearBtn.classList.toggle('hidden', !input.value);
    });
    clearBtn.addEventListener('click', function () {
      input.value = '';
      clearBtn.classList.add('hidden');
      input.focus();
    });
  }
  bindClear(searchInput, searchClear);
  bindClear(searchInputR, searchClearR);

  // ── Поиск ────────────────────────────────────────────────────
  var currentFilter = 'all';
  var currentPage   = 1;
  var allResults    = [];
  var pagefindInstance = null;
  var pendingQuery     = null;

  function initPagefind() {
    // Путь работает и локально (/pagefind/) и на Pages (/search/pagefind/)
    var base = window.location.pathname.startsWith('/search') ? '/search' : '';
    var script = document.createElement('script');
    script.type = 'module';
    script.textContent = [
      'import * as pagefind from "' + base + '/pagefind/pagefind.js";',
      'await pagefind.init();',
      'window.__pagefind__ = pagefind;',
      'window.dispatchEvent(new Event("pagefind-ready"));',
    ].join('\n');
    document.head.appendChild(script);
  }

  window.addEventListener('pagefind-ready', function () {
    pagefindInstance = window.__pagefind__;
    if (pendingQuery) {
      var q = pendingQuery;
      pendingQuery = null;
      doSearch(q);
    }
  });

  function doSearch(rawQuery) {
    if (!rawQuery.trim()) return;
    const query = normalizeQuery(rawQuery);
    setQueryParam('q', rawQuery);
    setQueryParam('page', '1');
    currentPage = 1;

    if (searchInputR) searchInputR.value = rawQuery;
    if (searchInput)  searchInput.value  = rawQuery;
    if (searchClear)  searchClear.classList.toggle('hidden', !rawQuery);
    if (searchClearR) searchClearR.classList.toggle('hidden', !rawQuery);

    showResults();
    renderSkeleton();

    if (!pagefindInstance) {
      pendingQuery = rawQuery;
      return;
    }

    pagefindInstance.search(query).then(function (res) {
      Promise.all(res.results.map(function (r) { return r.data(); }))
        .then(function (data) {
          allResults = data;
          renderResults();
        });
    }).catch(function () {
      renderError();
    });
  }

  // ── Фильтры ──────────────────────────────────────────────────
  if (filtersEl) {
    filtersEl.addEventListener('click', function (e) {
      const btn = e.target.closest('.filter');
      if (!btn) return;
      filtersEl.querySelectorAll('.filter').forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      currentPage   = 1;
      renderResults();
    });
  }

  // ── Источник из URL ──────────────────────────────────────────
  function getSource(result) {
    const url = result.url || '';
    if (url.includes('neerc.ifmo.ru'))    return 'neerc';
    if (url.includes('wikipedia.org'))   return 'wikipedia';
    if (url.includes('github.com'))      return 'github';
    if (url.includes('botaemeveryday'))  return 'notes';
    return 'other';
  }

  function getSourceLabel(source) {
    return { neerc: 'N', wikipedia: 'W', github: 'GH', notes: '✦', other: '?' }[source] || '?';
  }

  function getSourceName(url) {
    try { return new URL(url).hostname.replace('www.', ''); }
    catch { return url; }
  }

  function getPath(url) {
    try {
      const u = new URL(url);
      const parts = u.pathname.split('/').filter(Boolean);
      return parts.slice(0, 3).join(' · ');
    } catch { return ''; }
  }

  // ── Рендер результатов ───────────────────────────────────────
  var PER_PAGE = 10;

  function filterResults() {
    if (currentFilter === 'all') return allResults;
    return allResults.filter(function (r) { return getSource(r.meta) === currentFilter; });
  }

  function renderResults() {
    if (!resultsList) return;
    const filtered = filterResults();
    const total    = filtered.length;
    const start    = (currentPage - 1) * PER_PAGE;
    const page     = filtered.slice(start, start + PER_PAGE);

    if (resultsMeta) {
      resultsMeta.textContent = total
        ? 'около ' + total + ' ' + plural(total, 'результат', 'результата', 'результатов')
        : '';
    }

    if (!total) {
      resultsList.innerHTML = '<div class="results-empty">ничего не найдено<br><span style="font-size:12px">попробуйте другой запрос</span></div>';
      if (resultsPag) resultsPag.innerHTML = '';
      return;
    }

    resultsList.innerHTML = page.map(function (r) {
      const source  = getSource(r.meta);
      const label   = getSourceLabel(source);
      const host    = getSourceName(r.url);
      const path    = getPath(r.url);
      const isNotes = source === 'notes';
      const tags    = (r.meta && r.meta.tags) ? r.meta.tags.split(',') : [];

      return '<div class="result-item" onclick="window.open(\'' + escHtml(r.meta.url) + '\', \'_blank\')">'
        + '<div class="result-source-row">'
        + '<div class="result-favicon">' + label + '</div>'
        + '<span class="result-source"><span class="result-source-name">' + escHtml(host) + '</span>'
        + (path ? ' · ' + escHtml(path) : '')
        + '</span></div>'
        + '<div class="result-title">' + escHtml(r.meta && r.meta.title ? r.meta.title : r.url) + '</div>'
        + '<div class="result-snippet">' + (r.excerpt || '') + '</div>'
        + (tags.length || isNotes ? '<div class="result-tags">'
          + (isNotes ? '<span class="result-tag result-tag-accent">свой конспект</span>' : '')
          + tags.map(function (t) { return '<span class="result-tag">' + escHtml(t.trim()) + '</span>'; }).join('')
          + '</div>' : '')
        + '</div>';
    }).join('');

    renderPagination(total);
  }

  function renderPagination(total) {
    if (!resultsPag) return;
    const pages = Math.ceil(total / PER_PAGE);
    if (pages <= 1) { resultsPag.innerHTML = ''; return; }

    let html = '';
    for (let i = 1; i <= pages; i++) {
      html += '<button class="page-btn' + (i === currentPage ? ' active' : '') + '" data-page="' + i + '">' + i + '</button>';
    }
    resultsPag.innerHTML = html;
    resultsPag.querySelectorAll('.page-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        currentPage = parseInt(btn.dataset.page);
        setQueryParam('page', currentPage);
        renderResults();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    });
  }

  function renderSkeleton() {
    if (!resultsList) return;
    if (resultsMeta) resultsMeta.textContent = 'ищем...';
    resultsList.innerHTML = [1,2,3,4,5].map(function () {
      return '<div class="result-item">'
        + '<div class="skeleton" style="width:160px;height:12px;margin-bottom:8px"></div>'
        + '<div class="skeleton" style="width:80%;height:17px;margin-bottom:8px"></div>'
        + '<div class="skeleton" style="width:95%;height:12px;margin-bottom:4px"></div>'
        + '<div class="skeleton" style="width:70%;height:12px"></div>'
        + '</div>';
    }).join('');
  }

  function renderError() {
    if (!resultsList) return;
    resultsList.innerHTML = '<div class="results-empty">что-то пошло не так<br><span style="font-size:12px">попробуйте обновить страницу</span></div>';
  }

  // ── Утилиты ──────────────────────────────────────────────────
  function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function plural(n, one, few, many) {
    const mod10 = n % 10, mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11)               return one;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
    return many;
  }

  // ── Enter и кнопки ───────────────────────────────────────────
  function bindSearch(input) {
    if (!input) return;
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && input.value.trim()) doSearch(input.value);
    });
  }
  bindSearch(searchInput);
  bindSearch(searchInputR);

  if (btnSearch) btnSearch.addEventListener('click', function () {
    if (searchInput && searchInput.value.trim()) doSearch(searchInput.value);
  });

  if (btnLucky) btnLucky.addEventListener('click', function () {
    if (searchInput && searchInput.value.trim()) {
      doSearch(searchInput.value);
      // после загрузки — открываем первый результат
      setTimeout(function () {
        const first = document.querySelector('.result-item');
        if (first) first.click();
      }, 1000);
    }
  });

  if (searchInputR) {
    searchInputR.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && searchInputR.value.trim()) doSearch(searchInputR.value);
    });
  }

  // ── Восстановление из URL при загрузке ───────────────────────
  window.addEventListener('DOMContentLoaded', function () {
    const q    = getQueryParam('q');
    const page = parseInt(getQueryParam('page')) || 1;
    currentPage = page;

    initPagefind();

    if (q) {
      doSearch(q);
    }

    if (searchInput && !q) setTimeout(function () { searchInput.focus(); }, 100);
  });

  // ── Браузер назад/вперёд ─────────────────────────────────────
  window.addEventListener('popstate', function () {
    const q = getQueryParam('q');
    if (q) { doSearch(q); }
    else   { showHome(); }
  });

})();