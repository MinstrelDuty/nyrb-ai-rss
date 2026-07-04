(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  root.BookReviewCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function normalizeText(value) {
    return String(value || '').normalize('NFKC').toLocaleLowerCase();
  }

  function searchArticles(articles, query) {
    const needle = normalizeText(query).trim();
    if (!needle) return [...articles];

    return articles.filter(article => normalizeText([
      article.titleZh,
      article.titleEn,
      article.metaInfo,
      article.hook,
      article.contentText
    ].join('\n')).includes(needle));
  }

  function sanitizeFilename(value, maxLength = 80) {
    const cleaned = String(value || '未命名文章')
      .replace(/[\\/:*?"<>|\u0000-\u001f]/g, '-')
      .replace(/\s+/g, ' ')
      .replace(/-+/g, '-')
      .trim()
      .replace(/[. ]+$/g, '');
    return (cleaned || '未命名文章')
      .slice(0, maxLength)
      .replace(/[-. ]+$/g, '') || '未命名文章';
  }

  function yamlString(value) {
    return JSON.stringify(String(value || ''));
  }

  function buildArticleMarkdown(article, bodyMarkdown) {
    const title = article.titleZh || article.titleEn || '\u672a\u547d\u540d\u6587\u7ae0';
    const source = String(article.sourceId || article.sourceName || '').toUpperCase();
    const parts = [
      '---',
      `title: ${yamlString(title)}`,
      `original_title: ${yamlString(article.titleEn || '')}`,
      `source: ${yamlString(source)}`,
      `published: ${yamlString(article.publishedDate || '')}`,
      `original_url: ${yamlString(article.link || '')}`,
      'tags:',
      `  - ${yamlString('\u4e66\u8bc4')}`,
      `  - ${yamlString(source)}`,
      '---',
      '',
      `# ${title}`
    ];

    if (article.titleEn && article.titleEn !== title) parts.push('', `*${article.titleEn}*`);
    if (article.metaInfo) parts.push('', article.metaInfo);
    if (article.hook) parts.push('', `> ${article.hook}`);
    if (bodyMarkdown) parts.push('', bodyMarkdown.trim());
    if (article.link) parts.push('', `[\u9605\u8bfb\u82f1\u6587\u539f\u6587](${article.link})`);
    return `${parts.join('\n').trim()}\n`;
  }

  function buildIssueMarkdown(sourceName, isoDate, articles) {
    const parts = [
      `# ${sourceName} \u00b7 ${isoDate}`,
      '',
      `\u5171 ${articles.length} \u7bc7`,
      ''
    ];

    articles.forEach((article, index) => {
      const title = article.titleZh || article.titleEn || '\u672a\u547d\u540d\u6587\u7ae0';
      parts.push(`## ${index + 1}. ${title}`);
      if (article.titleEn && article.titleEn !== title) parts.push('', `*${article.titleEn}*`);
      if (article.metaInfo) parts.push('', article.metaInfo);
      if (article.hook) parts.push('', `> ${article.hook}`);
      if (article.bodyMarkdown) parts.push('', article.bodyMarkdown.trim());
      if (article.link) parts.push('', `[\u9605\u8bfb\u82f1\u6587\u539f\u6587](${article.link})`);
      if (index < articles.length - 1) parts.push('', '***', '');
    });

    return `${parts.join('\n').trim()}\n`;
  }

  return {
    normalizeText,
    searchArticles,
    sanitizeFilename,
    yamlString,
    buildArticleMarkdown,
    buildIssueMarkdown
  };
});
