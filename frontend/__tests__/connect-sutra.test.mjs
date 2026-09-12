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

test('OAuth authorization URL uses canonical API origin and never frontend origin', () => {
  assert.strictEqual(
    sutraConnect.CANONICAL_API_ORIGIN,
    'https://api.sutra.sudarshanai.com',
    'CANONICAL_API_ORIGIN constant must be exact canonical API origin'
  );
  assert.strictEqual(
    sutraConnect.CANONICAL_OAUTH_AUTHORIZE_ENDPOINT,
    'https://api.sutra.sudarshanai.com/oauth/authorize',
    'CANONICAL_OAUTH_AUTHORIZE_ENDPOINT must point to /oauth/authorize on API origin'
  );
  assert.strictEqual(
    sutraConnect.CANONICAL_OAUTH_CALLBACK_ENDPOINT,
    'https://api.sutra.sudarshanai.com/oauth/callback',
    'CANONICAL_OAUTH_CALLBACK_ENDPOINT must point to /oauth/callback on API origin'
  );

  const rawUrl = sutraConnect.getOAuthAuthorizeUrl();
  const parsed = new URL(rawUrl);

  assert.strictEqual(parsed.origin, 'https://api.sutra.sudarshanai.com', 'Authorization URL origin must be api.sutra.sudarshanai.com');
  assert.strictEqual(parsed.pathname, '/oauth/authorize', 'Authorization URL pathname must be /oauth/authorize');
  assert.notStrictEqual(parsed.origin, 'https://sutra.sudarshanai.com', 'Authorization URL origin must NOT be frontend sutra.sudarshanai.com');
  assert.strictEqual(rawUrl.startsWith('https://sutra.sudarshanai.com'), false, 'Authorization URL must never start with frontend origin');
  assert.strictEqual(rawUrl.startsWith('/oauth/authorize'), false, 'Authorization URL must never be a relative path');
});

test('OAuth authorization URL preserves explicit PKCE parameters when provided', () => {
  const rawUrl = sutraConnect.getOAuthAuthorizeUrl({
    state: 'sutra_browser_test',
    codeChallenge: 'E9Melhoa2OwvFrGMTJguCH5rtx64LxU408W32BgV16g',
    codeChallengeMethod: 'S256',
    scope: 'sutra:agent',
  });
  const parsed = new URL(rawUrl);
  const search = parsed.searchParams;

  assert.strictEqual(search.get('response_type'), 'code', 'Must include response_type=code');
  assert.strictEqual(search.get('client_id'), 'sutra-mcp-client', 'Must include client_id=sutra-mcp-client');
  assert.strictEqual(search.get('redirect_uri'), 'https://api.sutra.sudarshanai.com/oauth/callback', 'redirect_uri must be API callback endpoint');
  assert.strictEqual(search.get('state'), 'sutra_browser_test', 'Must preserve state parameter');
  assert.strictEqual(search.get('code_challenge'), 'E9Melhoa2OwvFrGMTJguCH5rtx64LxU408W32BgV16g', 'Must preserve code_challenge');
  assert.strictEqual(search.get('code_challenge_method'), 'S256', 'Must use code_challenge_method=S256');
  assert.strictEqual(search.get('scope'), 'sutra:agent', 'Must include scope=sutra:agent');
});

test('OAuth authorization URL generates a unique state per attempt when not specified', () => {
  const url1 = sutraConnect.getOAuthAuthorizeUrl();
  const url2 = sutraConnect.getOAuthAuthorizeUrl();
  const state1 = new URL(url1).searchParams.get('state');
  const state2 = new URL(url2).searchParams.get('state');

  assert.ok(state1, 'State 1 must be present');
  assert.ok(state2, 'State 2 must be present');
  assert.notStrictEqual(state1, state2, 'State must be unique across authorization attempts');
  assert.ok(state1.startsWith('sutra_test_'), 'State must carry sutra_test_ prefix');
  assert.ok(state2.startsWith('sutra_test_'), 'State must carry sutra_test_ prefix');
});

test('PKCE utility generates fresh verifiers and derives correct S256 challenge', async () => {
  const pkceModule = loadTsxModule('lib/pkce.ts');
  const session1 = await pkceModule.generatePkceSession();
  const session2 = await pkceModule.generatePkceSession();

  // Freshness & Uniqueness
  assert.notStrictEqual(session1.verifier, session2.verifier, 'Verifier must be cryptographically unique per attempt');
  assert.notStrictEqual(session1.challenge, session2.challenge, 'Challenge must be unique per attempt');
  assert.notStrictEqual(session1.state, session2.state, 'State must be unique per attempt');

  // Length requirements (RFC 7636 Section 4.1: 43 - 128 chars)
  assert.ok(session1.verifier.length >= 43 && session1.verifier.length <= 128, 'Verifier must satisfy RFC 7636 length requirements');

  // Cryptographic accuracy: S256 challenge must match SHA-256 base64url of verifier
  const expectedChallenge = await pkceModule.deriveCodeChallengeS256(session1.verifier);
  assert.strictEqual(session1.challenge, expectedChallenge, 'Derived S256 challenge must match SHA-256 hash of verifier');
});

test('Browser test session is stored strictly in sessionStorage, never in localStorage', async () => {
  const pkceModule = loadTsxModule('lib/pkce.ts');
  const session = await pkceModule.generatePkceSession();

  const mockSessionStorage = {};
  const mockLocalStorage = {};

  globalThis.window = {
    sessionStorage: {
      setItem: (k, v) => { mockSessionStorage[k] = v; },
      getItem: (k) => mockSessionStorage[k] || null,
      removeItem: (k) => { delete mockSessionStorage[k]; },
    },
    localStorage: {
      setItem: (k, v) => { mockLocalStorage[k] = v; },
      getItem: (k) => mockLocalStorage[k] || null,
      removeItem: (k) => { delete mockLocalStorage[k]; },
    },
  };

  try {
    pkceModule.saveBrowserTestSession(session);

    // Verify sessionStorage has the data
    const stored = pkceModule.getBrowserTestSession();
    assert.ok(stored, 'Session must be stored in sessionStorage');
    assert.strictEqual(stored.verifier, session.verifier, 'Stored verifier must match');
    assert.strictEqual(stored.state, session.state, 'Stored state must match');

    // Verify localStorage was NEVER touched
    assert.strictEqual(
      Object.keys(mockLocalStorage).length,
      0,
      'localStorage must NEVER contain verifiers, tokens, or codes'
    );

    // Clear session
    pkceModule.clearBrowserTestSession();
    assert.strictEqual(pkceModule.getBrowserTestSession(), null, 'Session must be cleared');
  } finally {
    delete globalThis.window;
  }
});

test('OAuth URL construction respects NEXT_PUBLIC_API_URL when configured', () => {
  const origEnv = process.env.NEXT_PUBLIC_API_URL;
  try {
    process.env.NEXT_PUBLIC_API_URL = 'https://custom-api.example.com';
    const rawUrl = sutraConnect.getOAuthAuthorizeUrl();
    const parsed = new URL(rawUrl);

    assert.strictEqual(parsed.origin, 'https://custom-api.example.com', 'Must respect configured NEXT_PUBLIC_API_URL');
    assert.strictEqual(parsed.searchParams.get('redirect_uri'), 'https://custom-api.example.com/oauth/callback', 'Must adjust redirect_uri to configured API origin');
  } finally {
    if (origEnv !== undefined) {
      process.env.NEXT_PUBLIC_API_URL = origEnv;
    } else {
      delete process.env.NEXT_PUBLIC_API_URL;
    }
  }
});

test('ConnectSutraModal renders OAuth launch link pointing to canonical API origin, never relative path', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(sutraConnect.ConnectSutraModal, {
      isOpen: true,
      onClose: () => {},
      connectionState: 'not_connected',
    })
  );

  assert.ok(
    html.includes('href="https://api.sutra.sudarshanai.com/oauth/authorize?'),
    'Modal link must point directly to canonical API authorize endpoint'
  );
  assert.strictEqual(
    html.includes('href="/oauth/authorize'),
    false,
    'Modal link must never use a relative path /oauth/authorize'
  );
  assert.strictEqual(
    html.includes('href="https://sutra.sudarshanai.com/oauth/authorize'),
    false,
    'Modal link must never point to the frontend domain'
  );
  assert.ok(
    html.includes('Test Browser OAuth Authorization Flow'),
    'Must render link text "Test Browser OAuth Authorization Flow"'
  );
});

