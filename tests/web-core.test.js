const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../web-core.js');

const articles = [
  {
    sourceId: 'nyrb',
    titleZh: '自由的代价',
    titleEn: 'The Cost of Freedom',
    metaInfo: '作者：A',
    hook: '政治与记忆',
    contentText: '一段关于历史记忆的正文'
  },
  {
    sourceId: 'lrb',
    titleZh: '城市漫游',
    titleEn: 'Walking the City',
    metaInfo: '作者：B',
    hook: '现代生活',
    contentText: '城市空间与文学'
  }
];

test('searches Chinese text across normalized article fields', () => {
  assert.deepEqual(core.searchArticles(articles, '历史').map(item => item.sourceId), ['nyrb']);
});

test('search is case-insensitive for English', () => {
  assert.equal(core.searchArticles(articles, 'FREEDOM').length, 1);
});

test('searches author metadata', () => {
  assert.deepEqual(core.searchArticles(articles, '作者：B').map(item => item.sourceId), ['lrb']);
});

test('empty search returns all articles', () => {
  assert.equal(core.searchArticles(articles, '  ').length, 2);
});

test('sanitizes Windows-invalid filename characters and length', () => {
  assert.equal(core.sanitizeFilename('A:B/C*D?E"F<G>H|I', 12), 'A-B-C-D-E-F');
});
