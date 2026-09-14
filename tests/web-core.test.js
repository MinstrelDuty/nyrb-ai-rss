const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const { escapeRawHtml, isSafeUrl, searchArticles } = require('../web-core.js');

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

test('isSafeUrl allows only HTTP(S) URLs for publisher-controlled links', () => {
  assert.equal(isSafeUrl('https://www.lrb.co.uk/article'), true);
  assert.equal(isSafeUrl('javascript:alert(1)'), false);
  assert.equal(isSafeUrl('data:text/html,alert(1)'), false);
});

test('frontend registers New Yorker and Atlantic as distinct sources', () => {
  const app = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
  assert.match(app, /\{ id: 'newyorker', shortName: 'NEW YORKER', name: '纽约客' \}/);
  assert.match(app, /\{ id: 'atlantic', shortName: 'ATLANTIC', name: '大西洋月刊' \}/);
  assert.match(app, /getSource\(String\(record\.source \|\| ''\)\.toLowerCase\(\)\)/);
});

test('frontend exposes six-source navigation and archive wording', () => {
  const index = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
  assert.match(index, /data-source="newyorker">纽约客/);
  assert.match(index, /data-source="atlantic">大西洋月刊/);
  assert.match(index, /六种书评刊物/);
  assert.match(index, /全部六刊/);
  assert.match(index, /下载全部六刊归档/);
});
