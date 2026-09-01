const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');

const app = fs.readFileSync('app.js', 'utf8');
const html = fs.readFileSync('index.html', 'utf8');

for (const [id, file, label] of [
  ['newyorker', 'newyorker_ai_enhanced.xml', '纽约客'],
  ['atlantic', 'atlantic_ai_enhanced.xml', '大西洋月刊'],
  ['larb', 'larb_ai_enhanced.xml', '洛杉矶书评'],
  ['publicbooks', 'publicbooks_ai_enhanced.xml', 'Public Books'],
]) {
  test(`contains ${id} source in app and navigation`, () => {
    assert.match(app, new RegExp(`id: '${id}'`));
    assert.match(app, new RegExp(`file: '${file}'`));
    assert.match(html, new RegExp(`data-source="${id}"`));
    assert.match(html, new RegExp(label));
  });
}

test('uses eight-source labels for all-source search and archive actions', () => {
  assert.match(html, /全部八刊/);
  assert.match(html, /全部八刊归档/);
  assert.match(app, /正在整理八刊/);
  assert.doesNotMatch(html, /全部四刊/);
  assert.doesNotMatch(app, /整理四刊/);
});

test('uses content encoded HTML when a structured feed omits inline body text', () => {
  assert.match(app, /const encodedHtml = encodedNode\?\.textContent\?\.trim\(\) \|\| ''/);
  assert.match(app, /contentHtml = encodedHtml \|\|/);
});
