const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../web-core.js');

test('quotes YAML string values safely', () => {
  assert.equal(core.yamlString('A "quoted" title'), '"A \\"quoted\\" title"');
});

test('builds an Obsidian article note with frontmatter and original link', () => {
  const note = core.buildArticleMarkdown({
    sourceId: 'NYRB',
    sourceName: '纽约书评',
    titleZh: '自由的代价',
    titleEn: 'The Cost of Freedom',
    publishedDate: '2026-07-02',
    link: 'https://example.com/a',
    metaInfo: '作者：A',
    hook: '政治与记忆'
  }, '### 核心脉络\n\n正文');

  assert.match(note, /title: "自由的代价"/);
  assert.match(note, /source: "NYRB"/);
  assert.match(note, /original_url: "https:\/\/example.com\/a"/);
  assert.match(note, /  - "书评"/);
  assert.match(note, /# 自由的代价/);
  assert.match(note, /\[阅读英文原文\]\(https:\/\/example.com\/a\)/);
});

test('builds a single issue Markdown document without frontmatter', () => {
  const output = core.buildIssueMarkdown('纽约书评', '2026-07-02', [{
    titleZh: '第一篇',
    titleEn: 'First Article',
    metaInfo: '作者：A',
    hook: '一个洞见',
    link: 'https://example.com/first',
    bodyMarkdown: '正文一'
  }]);

  assert.match(output, /^# 纽约书评 · 2026-07-02/m);
  assert.match(output, /## 1\. 第一篇/);
  assert.match(output, /正文一/);
  assert.doesNotMatch(output, /^---$/m);
});
