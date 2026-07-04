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

  return {
    normalizeText,
    searchArticles,
    sanitizeFilename
  };
});
