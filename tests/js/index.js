'use strict';
/**
 * `node --test tests/js/` — with Node 22 a directory argument is run as ONE module, which is
 * this file: it loads every *.test.mjs of the directory. (`node --test "tests/js/*.test.mjs"`
 * runs the same tests file by file.)
 */
const { readdirSync } = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const files = readdirSync(__dirname).filter((name) => name.endsWith('.test.mjs')).sort();
(async () => {
  for (const name of files) await import(pathToFileURL(path.join(__dirname, name)).href);
})();
