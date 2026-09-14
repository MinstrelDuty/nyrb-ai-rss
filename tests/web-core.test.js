const assert = require('node:assert/strict');
const test = require('node:test');

const { escapeRawHtml, searchArticles } = require('../web-core.js');

test('searchArticles finds an article through a keyword', () => {
  const articles = [{
    title_zh: '细读的必要性',
    original_title: 'Good Weird or Bad Weird',
    author: 'Colin Burrow',
    subject: '文学批评',
    hook: '一篇关于批评的文章。',
    keywords: ['close reading', 'criticism'],
    body_markdown: '正文不包含目标检索词。'
  }];

  assert.deepEqual(searchArticles(articles, 'close reading'), articles);
});

test('escapeRawHtml prevents published Markdown from injecting HTML', () => {
  assert.equal(
    escapeRawHtml('<img src=x onerror="alert(1)">'),
    '&lt;img src=x onerror="alert(1)"&gt;'
  );
});
