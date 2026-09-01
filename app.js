(function () {
  'use strict';

  const SOURCES = [
    { id: 'nyrb', shortName: 'NYRB', name: '纽约书评', file: 'nyrb_ai_enhanced.xml' },
    { id: 'lrb', shortName: 'LRB', name: '伦敦书评', file: 'lrb_ai_enhanced.xml' },
    { id: 'tls', shortName: 'TLS', name: '泰晤士文学增刊', file: 'tls_ai_enhanced.xml' },
    { id: 'nyt', shortName: 'NYT', name: '纽时书评', file: 'nyt_ai_enhanced.xml' },
    { id: 'newyorker', shortName: 'NEWYORKER', name: '纽约客', file: 'newyorker_ai_enhanced.xml' },
    { id: 'atlantic', shortName: 'ATLANTIC', name: '大西洋月刊', file: 'atlantic_ai_enhanced.xml' },
    { id: 'larb', shortName: 'LARB', name: '洛杉矶书评', file: 'larb_ai_enhanced.xml' },
    { id: 'publicbooks', shortName: 'PUBLICBOOKS', name: 'Public Books', file: 'publicbooks_ai_enhanced.xml' }
  ];

  const feedCache = new Map();
  const turndown = typeof TurndownService !== 'undefined'
    ? new TurndownService({ headingStyle: 'atx', codeBlockStyle: 'fenced', bulletListMarker: '-' })
    : null;

  let activeSourceId = 'nyrb';
  let searchScope = 'current';
  let searchTimer = null;
  let currentArticles = [];

  const contentEl = document.getElementById('content');
  const searchInput = document.getElementById('searchInput');
  const resultCount = document.getElementById('resultCount');
  const noticeEl = document.getElementById('notice');
  const currentArchiveButton = document.getElementById('downloadCurrentArchive');
  const allArchiveButton = document.getElementById('downloadAllArchive');

  function getSource(sourceId) {
    return SOURCES.find(source => source.id === sourceId) || SOURCES[0];
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function escapeRegex(value) {
    return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function highlightText(value, query) {
    const text = String(value || '');
    const needle = String(query || '').trim();
    if (!needle) return escapeHtml(text);
    const regex = new RegExp(`(${escapeRegex(needle)})`, 'ig');
    return text.split(regex)
      .map((part, index) => index % 2 ? `<mark>${escapeHtml(part)}</mark>` : escapeHtml(part))
      .join('');
  }

  function stripHtml(html) {
    const element = document.createElement('div');
    element.innerHTML = html || '';
    return element.textContent || element.innerText || '';
  }

  function extractSection(text, header) {
    const regex = new RegExp(`【${escapeRegex(header)}】[:：\\s]*([^【]+)`);
    const match = String(text || '').match(regex);
    return match ? match[1].trim() : '';
  }

  function safeDate(value) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return { timestamp: 0, iso: '未知日期', label: '未知日期' };
    }
    return {
      timestamp: parsed.getTime(),
      iso: parsed.toISOString().slice(0, 10),
      label: parsed.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
    };
  }

  function parseArticle(item, source) {
    const titleEn = item.querySelector('title')?.textContent?.trim() || 'Untitled';
    const pubDate = item.querySelector('pubDate')?.textContent || '';
    const link = item.querySelector('link')?.textContent?.trim() || '#';
    const description = item.querySelector('description')?.textContent || '';
    const encodedNode = item.getElementsByTagNameNS('*', 'encoded')[0];
    const date = safeDate(pubDate);

    let titleZh = '';
    let metaInfo = '';
    let hook = '';
    let contentHtml = '';

    if (description.includes('|||')) {
      const parts = description.split('|||');
      titleZh = parts[0]?.trim() || '解析失败';
      metaInfo = parts[1]?.trim() || '';
      hook = parts[2]?.trim() || '';
      contentHtml = encodedNode?.textContent || '<p>无正文</p>';
    } else if (description.includes('未能成功抓取') || description.includes('AI 处理超时')) {
      titleZh = '原文特殊或抓取受限';
      metaInfo = '系统提示';
      hook = '该文章未能完成自动精读';
      contentHtml = `<p>${escapeHtml(description)}</p>`;
    } else {
      titleZh = extractSection(description, '中文标题');
      metaInfo = extractSection(description, '作者与对象');
      hook = extractSection(description, '一句话破题');

      if (!titleZh) titleZh = titleEn;

      const contentParts = description.split(/【正文】/);
      const markdownText = (contentParts.length > 1 ? contentParts[1] : description)
        .replace(/<hr>\s*<i>注：.*?<\/i>/g, '')
        .trim();
      contentHtml = window.marked ? marked.parse(markdownText) : `<pre>${escapeHtml(markdownText)}</pre>`;
    }

    return {
      sourceId: source.shortName,
      sourceKey: source.id,
      sourceName: source.name,
      titleZh,
      titleEn,
      metaInfo,
      hook,
      contentHtml,
      contentText: stripHtml(contentHtml),
      link,
      publishedAt: date.timestamp,
      publishedDate: date.iso,
      dateLabel: date.label
    };
  }

  async function loadSource(source) {
    if (feedCache.has(source.id)) return feedCache.get(source.id);

    const promise = fetch(`${source.file}?t=${Date.now()}`)
      .then(response => {
        if (!response.ok) throw new Error(`${source.name} 加载失败 (${response.status})`);
        return response.text();
      })
      .then(xmlText => {
        const documentXml = new DOMParser().parseFromString(xmlText, 'text/xml');
        if (documentXml.querySelector('parsererror')) throw new Error(`${source.name} XML 解析失败`);
        const articles = Array.from(documentXml.querySelectorAll('item'))
          .map(item => parseArticle(item, source))
          .sort((a, b) => b.publishedAt - a.publishedAt);
        return articles;
      })
      .catch(error => {
        feedCache.delete(source.id);
        throw error;
      });

    feedCache.set(source.id, promise);
    return promise;
  }

  async function loadAllSources() {
    const settled = await Promise.allSettled(SOURCES.map(source => loadSource(source)));
    const articles = [];
    const errors = [];

    settled.forEach((result, index) => {
      if (result.status === 'fulfilled') articles.push(...result.value);
      else errors.push(`${SOURCES[index].name}：${result.reason?.message || '加载失败'}`);
    });

    articles.sort((a, b) => b.publishedAt - a.publishedAt);
    return { articles, errors };
  }

  function setNotice(message, type = '') {
    noticeEl.textContent = message || '';
    noticeEl.className = `notice ${type}`.trim();
    noticeEl.hidden = !message;
  }

  function setLoading(message) {
    contentEl.innerHTML = `<div class="loading">${escapeHtml(message)}</div>`;
  }

  function articleCard(article, options = {}) {
    const query = options.query || '';
    const showSource = Boolean(options.showSource);
    const titleZh = query ? highlightText(article.titleZh, query) : escapeHtml(article.titleZh);
    const titleEn = query ? highlightText(article.titleEn, query) : escapeHtml(article.titleEn);
    const metaInfo = query ? highlightText(article.metaInfo, query) : escapeHtml(article.metaInfo);
    const hook = query ? highlightText(article.hook, query) : escapeHtml(article.hook);
    let snippet = '';

    if (query) {
      const text = article.contentText || '';
      const index = text.toLocaleLowerCase().indexOf(query.toLocaleLowerCase());
      const start = Math.max(0, index > -1 ? index - 45 : 0);
      const excerpt = `${start > 0 ? '…' : ''}${text.slice(start, start + 150)}${text.length > start + 150 ? '…' : ''}`;
      snippet = `<p class="search-snippet">${highlightText(excerpt, query)}</p>`;
    }

    return `
      <article class="article-card" data-source="${escapeHtml(article.sourceKey)}">
        <button class="article-header" type="button" aria-expanded="false">
          <span class="article-title-wrap">
            ${showSource ? `<span class="source-badge">${escapeHtml(article.sourceId)}</span>` : ''}
            <span class="article-title-en">${titleEn}</span>
            <span class="article-title-zh">${titleZh}</span>
            ${metaInfo ? `<span class="article-meta-author">${metaInfo}</span>` : ''}
            ${hook ? `<span class="article-hook">🎯 ${hook}</span>` : ''}
            ${snippet}
            <span class="article-meta">
              <span>${escapeHtml(article.dateLabel)}</span>
              <a href="${escapeHtml(article.link)}" target="_blank" rel="noopener" class="original-link">阅读原刊</a>
            </span>
          </span>
          <span class="toggle-icon" aria-hidden="true">⌄</span>
        </button>
        <div class="article-body">
          <div class="article-content">${article.contentHtml}</div>
        </div>
      </article>`;
  }

  function groupByDate(articles) {
    const groups = new Map();
    articles.forEach(article => {
      if (!groups.has(article.publishedDate)) groups.set(article.publishedDate, []);
      groups.get(article.publishedDate).push(article);
    });
    return groups;
  }

  function renderIssueGroups(articles) {
    currentArticles = articles;
    resultCount.textContent = `共 ${articles.length} 篇`;
    if (!articles.length) {
      contentEl.innerHTML = '<div class="empty-state">暂时没有文章。</div>';
      return;
    }

    const html = [];
    for (const [date, issueArticles] of groupByDate(articles)) {
      html.push(`
        <section class="issue-group">
          <div class="issue-header">
            <h2 class="issue-title">📅 ${escapeHtml(issueArticles[0].dateLabel)} · 共 ${issueArticles.length} 篇</h2>
            <button class="download-btn" type="button" data-date="${escapeHtml(date)}">下载本期 (.md)</button>
          </div>
          ${issueArticles.map(article => articleCard(article)).join('')}
        </section>`);
    }
    contentEl.innerHTML = html.join('');
  }

  function renderSearchResults(articles, query, showSource) {
    resultCount.textContent = `找到 ${articles.length} 篇`;
    if (!articles.length) {
      contentEl.innerHTML = `<div class="empty-state">没有找到与“${escapeHtml(query)}”相关的内容。</div>`;
      return;
    }
    contentEl.innerHTML = `
      <section class="search-results">
        <div class="search-heading">全文检索结果</div>
        ${articles.map(article => articleCard(article, { query, showSource })).join('')}
      </section>`;
  }

  async function showActiveSource() {
    const source = getSource(activeSourceId);
    setNotice('');
    setLoading(`正在加载${source.name}…`);
    try {
      const articles = await loadSource(source);
      renderIssueGroups(articles);
    } catch (error) {
      contentEl.innerHTML = `<div class="empty-state error">${escapeHtml(error.message)}</div>`;
    }
  }

  async function runSearch() {
    const query = searchInput.value.trim();
    if (!query) {
      await showActiveSource();
      return;
    }

    setLoading('正在检索全部正文…');
    try {
      if (searchScope === 'all') {
        const { articles, errors } = await loadAllSources();
        const matches = BookReviewCore.searchArticles(articles, query);
        renderSearchResults(matches, query, true);
        setNotice(errors.length ? `部分来源加载失败：${errors.join('；')}` : '');
      } else {
        const articles = await loadSource(getSource(activeSourceId));
        renderSearchResults(BookReviewCore.searchArticles(articles, query), query, false);
        setNotice('');
      }
    } catch (error) {
      contentEl.innerHTML = `<div class="empty-state error">${escapeHtml(error.message)}</div>`;
    }
  }

  function scheduleSearch() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, 180);
  }

  function bodyMarkdown(article) {
    if (!turndown) throw new Error('Markdown 转换组件未加载');
    return turndown.turndown(article.contentHtml || '');
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadText(text, filename) {
    downloadBlob(new Blob(['\uFEFF', text], { type: 'text/markdown;charset=utf-8' }), filename);
  }

  async function withBusyButton(button, busyLabel, operation) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = busyLabel;
    try {
      await operation();
    } catch (error) {
      console.error(error);
      alert(error.message || '操作失败，请稍后重试。');
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function archiveReadme(sourceResults, errors) {
    const total = sourceResults.reduce((sum, result) => sum + result.articles.length, 0);
    const lines = [
      '# 书评深度集萃 · Obsidian 归档',
      '',
      `生成时间：${new Date().toLocaleString('zh-CN')}`,
      `文章总数：${total}`,
      '',
      '## 来源'
    ];
    sourceResults.forEach(result => lines.push(`- ${result.source.name}：${result.articles.length} 篇`));
    if (errors.length) {
      lines.push('', '## 未能加载的来源');
      errors.forEach(error => lines.push(`- ${error}`));
    }
    lines.push('', '每篇文章均包含 YAML 元数据，可直接放入 Obsidian Vault。', '');
    return lines.join('\n');
  }

  async function buildArchive(sourceResults, errors = []) {
    if (typeof JSZip === 'undefined') throw new Error('ZIP 组件未加载');
    const total = sourceResults.reduce((sum, result) => sum + result.articles.length, 0);
    if (!total) throw new Error('没有可归档的文章');

    const zip = new JSZip();
    const root = zip.folder('书评深度集萃');
    root.file('README.md', archiveReadme(sourceResults, errors));

    sourceResults.forEach(({ source, articles }) => {
      const sourceFolder = root.folder(source.shortName);
      groupByDate(articles).forEach((dateArticles, date) => {
        const dateFolder = sourceFolder.folder(date);
        dateArticles.forEach((article, index) => {
          const title = BookReviewCore.sanitizeFilename(article.titleZh || article.titleEn, 70);
          const filename = `${String(index + 1).padStart(2, '0')}-${title}.md`;
          const note = BookReviewCore.buildArticleMarkdown(article, bodyMarkdown(article));
          dateFolder.file(filename, note);
        });
      });
    });

    return zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } });
  }

  function todayIso() {
    return BookReviewCore.localDateIso();
  }

  async function downloadIssue(button) {
    const date = button.dataset.date;
    const source = getSource(activeSourceId);
    const articles = (await loadSource(source)).filter(article => article.publishedDate === date);
    if (!articles.length) throw new Error('本期没有可下载文章');
    const prepared = articles.map(article => ({ ...article, bodyMarkdown: bodyMarkdown(article) }));
    const markdown = BookReviewCore.buildIssueMarkdown(source.name, date, prepared);
    downloadText(markdown, `${BookReviewCore.sanitizeFilename(source.name)}-${date}.md`);
  }

  async function downloadCurrentArchive(button) {
    const source = getSource(activeSourceId);
    const articles = await loadSource(source);
    const blob = await buildArchive([{ source, articles }]);
    downloadBlob(blob, `书评深度集萃-${source.shortName}-归档-${todayIso()}.zip`);
  }

  async function downloadAllArchive(button) {
    const settled = await Promise.allSettled(SOURCES.map(source => loadSource(source)));
    const sourceResults = [];
    const errors = [];
    settled.forEach((result, index) => {
      if (result.status === 'fulfilled') sourceResults.push({ source: SOURCES[index], articles: result.value });
      else errors.push(`${SOURCES[index].name}：${result.reason?.message || '加载失败'}`);
    });
    const blob = await buildArchive(sourceResults, errors);
    downloadBlob(blob, `书评深度集萃-全部归档-${todayIso()}.zip`);
  }

  document.querySelector('.nav-tabs').addEventListener('click', async event => {
    const button = event.target.closest('.nav-btn');
    if (!button) return;
    document.querySelectorAll('.nav-btn').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    activeSourceId = button.dataset.source;
    if (searchInput.value.trim()) await runSearch();
    else await showActiveSource();
  });

  document.querySelector('.scope-switch').addEventListener('click', event => {
    const button = event.target.closest('.scope-btn');
    if (!button) return;
    document.querySelectorAll('.scope-btn').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    searchScope = button.dataset.scope;
    scheduleSearch();
  });

  searchInput.addEventListener('input', scheduleSearch);

  contentEl.addEventListener('click', event => {
    const originalLink = event.target.closest('.original-link');
    if (originalLink) return;

    const downloadButton = event.target.closest('.download-btn');
    if (downloadButton) {
      withBusyButton(downloadButton, '正在生成…', () => downloadIssue(downloadButton));
      return;
    }

    const header = event.target.closest('.article-header');
    if (!header) return;
    const card = header.closest('.article-card');
    const isOpen = card.classList.toggle('open');
    header.setAttribute('aria-expanded', String(isOpen));
  });

  currentArchiveButton.addEventListener('click', () => {
    withBusyButton(currentArchiveButton, '正在整理…', () => downloadCurrentArchive(currentArchiveButton));
  });

  allArchiveButton.addEventListener('click', () => {
    withBusyButton(allArchiveButton, '正在整理四刊…', () => downloadAllArchive(allArchiveButton));
  });

  window.addEventListener('DOMContentLoaded', showActiveSource);
})();
