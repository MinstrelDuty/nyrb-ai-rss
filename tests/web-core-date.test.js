const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../web-core.js');

test('formats the local calendar date without converting to UTC', () => {
  const localDate = {
    getFullYear: () => 2026,
    getMonth: () => 6,
    getDate: () => 5
  };
  assert.equal(core.localDateIso(localDate), '2026-07-05');
});
