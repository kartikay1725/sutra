import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import ts from 'typescript';
import vm from 'node:vm';
import React from 'react';
import ReactDOMServer from 'react-dom/server';

const require = createRequire(import.meta.url);

function loadTsxModule(relPath) {
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
  const req = (id) => {
    if (id.startsWith('.')) {
      const resolved = path.resolve(path.dirname(fullPath), id);
      if (fs.existsSync(resolved + '.tsx')) return loadTsxModule(resolved + '.tsx');
      if (fs.existsSync(resolved + '.ts')) return loadTsxModule(resolved + '.ts');
      if (fs.existsSync(resolved)) return loadTsxModule(resolved);
    }
    return require(id);
  };

  const fn = vm.runInThisContext(
    '(function(exports, require, module, __filename, __dirname) { ' + transpiled + '\n})',
    { filename: fullPath }
  );
  fn(mod.exports, req, mod, fullPath, path.dirname(fullPath));
  return mod.exports;
}

const sutraConnect = loadTsxModule('components/sutra-connect.tsx');

test('Connect button renders with primary CTA and Zap icon', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(sutraConnect.ConnectSutraButton, {
      onClick: () => {},
      state: 'not_connected',
    })
  );

  assert.ok(html.includes('Connect SUTRA'), 'Must render "Connect SUTRA" CTA text');
  assert.ok(html.includes('sutra-connect-btn'), 'Must have button class sutra-connect-btn');
  assert.ok(html.includes('lucide-zap'), 'Must render Zap icon');
  assert.strictEqual(html.includes('sutra_agent_'), false, 'Must not render any agent tokens');
});

test('Fallback cards render when client is unsupported', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(sutraConnect.ConnectSutraModal, {
      isOpen: true,
      onClose: () => {},
      connectionState: 'unsupported',
    })
  );

  // Card 1: Custom MCP Settings
  assert.ok(html.includes('Custom MCP Settings'), 'Must render Card 1: Custom MCP Settings');
  assert.ok(
    html.includes('Point your client to the canonical SUTRA MCP endpoint'),
    'Must explain remote MCP server behavior'
  );

  // Card 2: API Integration
  assert.ok(html.includes('API Integration'), 'Must render Card 2: API Integration');
  assert.ok(
    html.includes('Fallback for automated pipelines'),
    'Must explain API Integration fallback'
  );
  assert.ok(html.includes('/docs'), 'Must link to SUTRA API documentation (/docs)');

  // Clear distinction of connection methods
  assert.ok(html.includes('1. Automatic Connection'), 'Must list Automatic Connection method');
  assert.ok(html.includes('2. Custom MCP Configuration'), 'Must list Custom MCP Configuration method');
  assert.ok(html.includes('3. API Integration'), 'Must list API Integration method');
});

test('MCP endpoint is correct and canonical', () => {
  assert.strictEqual(
    sutraConnect.CANONICAL_MCP_ENDPOINT,
    'https://api.sutra.sudarshanai.com/v1/mcp',
    'CANONICAL_MCP_ENDPOINT constant must be exact production canonical URL'
  );

  const html = ReactDOMServer.renderToString(
    React.createElement(sutraConnect.ConnectSutraModal, {
      isOpen: true,
      onClose: () => {},
      connectionState: 'unsupported',
    })
  );

  assert.ok(
    html.includes('https://api.sutra.sudarshanai.com/v1/mcp'),
    'Rendered HTML must expose canonical endpoint https://api.sutra.sudarshanai.com/v1/mcp'
  );
});

test('No secret, database credential, or agent token is rendered', () => {
  const buttonHtml = ReactDOMServer.renderToString(
    React.createElement(sutraConnect.ConnectSutraButton, {
      onClick: () => {},
      state: 'not_connected',
    })
  );

  const modalHtml = ReactDOMServer.renderToString(
    React.createElement(sutraConnect.ConnectSutraModal, {
      isOpen: true,
      onClose: () => {},
      connectionState: 'unsupported',
    })
  );

  const combined = buttonHtml + modalHtml;

  assert.strictEqual(combined.includes('sutra_agent_'), false, 'Must not expose sutra_agent_ tokens');
  assert.strictEqual(combined.includes('sutra_session_'), false, 'Must not expose sutra_session_ tokens');
  assert.strictEqual(combined.includes('YOUR_SUTRA_TOKEN'), false, 'Must not expose YOUR_SUTRA_TOKEN placeholder');
  assert.strictEqual(combined.includes('postgres://'), false, 'Must not expose database credentials');
  assert.strictEqual(combined.includes('BEGIN PRIVATE KEY'), false, 'Must not expose private keys');
});

test('Connected state renders correctly with active status', () => {
  // Test button in connected state
  const buttonConnectedHtml = ReactDOMServer.renderToString(
    React.createElement(sutraConnect.ConnectSutraButton, {
      onClick: () => {},
      state: 'connected',
    })
  );
  assert.ok(buttonConnectedHtml.includes('SUTRA Connected'), 'Button must show "SUTRA Connected"');
  assert.ok(buttonConnectedHtml.includes('connected'), 'Button must include connected CSS class');

  // Test modal in connected state with agent name
  const modalConnectedHtml = ReactDOMServer.renderToString(
    React.createElement(sutraConnect.ConnectSutraModal, {
      isOpen: true,
      onClose: () => {},
      connectionState: 'connected',
      connectedAgentName: 'Cursor Agent Pro',
    })
  );
  assert.ok(modalConnectedHtml.includes('Connected (Cursor Agent Pro)'), 'Modal must reflect connected state with agent name');
  assert.ok(modalConnectedHtml.includes('Disconnect'), 'Modal must provide Disconnect action');
});
