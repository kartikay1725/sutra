import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import ts from 'typescript';
import vm from 'node:vm';

const require = createRequire(import.meta.url);

function loadTsModule(relPath) {
  const fullPath = path.resolve(process.cwd(), relPath);
  const code = fs.readFileSync(fullPath, 'utf8');
  const transpiled = ts.transpileModule(code, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;

  const mod = { exports: {} };
  const fn = vm.runInThisContext(
    '(function(exports, require, module, __filename, __dirname) { ' + transpiled + '\n})',
    { filename: fullPath }
  );
  fn(mod.exports, require, mod, fullPath, path.dirname(fullPath));
  return mod.exports;
}

test('getApiUrl uses the same-origin API proxy in the browser', () => {
  const previousEnv = process.env.NEXT_PUBLIC_API_URL;
  const previousWindow = globalThis.window;

  delete process.env.NEXT_PUBLIC_API_URL;
  globalThis.window = { location: { hostname: 'sutra.sudarshanai.com' } };

  try {
    const api = loadTsModule('lib/api.ts');
    assert.strictEqual(api.getApiUrl(), '/api');
  } finally {
    if (previousEnv === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = previousEnv;
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});
