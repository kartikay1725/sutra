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
    if (id.startsWith('@/')) {
      const sub = id.slice(2);
      const candidates = [
        path.resolve(process.cwd(), sub + '.tsx'),
        path.resolve(process.cwd(), sub + '.ts'),
        path.resolve(process.cwd(), sub),
      ];
      for (const c of candidates) {
        if (fs.existsSync(c)) return loadTsxModule(path.relative(process.cwd(), c));
      }
    }
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

const sutraInstructions = loadTsxModule('lib/sutra-instructions.ts');
const sutraComponent = loadTsxModule('components/SutraAgentInstructions.tsx');
const groupMcpModule = loadTsxModule('app/docs/content/groupMcp.tsx');
const docsDataModule = loadTsxModule('app/docs/content/data.tsx');

test('Canonical instruction block exports expected version and metadata', () => {
  assert.strictEqual(sutraInstructions.SUTRA_INSTRUCTION_BLOCK_ID, 'sutra-engineering-policy');
  assert.strictEqual(sutraInstructions.SUTRA_INSTRUCTION_VERSION, 1);
  assert.strictEqual(sutraInstructions.SUTRA_RECOMMENDED_FILE, 'AGENTS.md');
  assert.ok(Array.isArray(sutraInstructions.SUTRA_SUPPORTED_TARGETS));
  assert.ok(sutraInstructions.SUTRA_SUPPORTED_TARGETS.some((t) => t.name === 'AGENTS.md' && t.recommended));
  assert.ok(sutraInstructions.SUTRA_SUPPORTED_TARGETS.some((t) => t.name === 'CLAUDE.md'));
  assert.ok(sutraInstructions.SUTRA_SUPPORTED_TARGETS.some((t) => t.name === 'Cursor Rules'));
});

test('Canonical instruction block content matches exact required structure', () => {
  const block = sutraInstructions.SUTRA_CANONICAL_INSTRUCTION_BLOCK;
  assert.ok(block.includes('<!-- SUTRA:START id=sutra-engineering-policy version=1 -->'), 'Must have opening delimiter');
  assert.ok(block.includes('## SUTRA Engineering Control'), 'Must have header');
  assert.ok(block.includes('SUTRA is the engineering control plane for this repository.'), 'Must state control plane');
  assert.ok(block.includes('sutra_start_task'), 'Must mention sutra_start_task');
  assert.ok(block.includes('sutra_declare_change'), 'Must mention sutra_declare_change');
  assert.ok(block.includes('sutra_push_commit'), 'Must mention sutra_push_commit');
  assert.ok(block.includes('sutra_open_pull_request'), 'Must mention sutra_open_pull_request');
  assert.ok(block.includes('sutra_get_status'), 'Must mention sutra_get_status');
  assert.ok(block.includes('sutra_get_provenance'), 'Must mention sutra_get_provenance');
  assert.ok(block.includes('sutra_get_governance'), 'Must mention sutra_get_governance');
  assert.ok(block.includes('sutra_complete_task'), 'Must mention sutra_complete_task');
  assert.ok(block.includes('`git commit`'), 'Must mention terminal git commit');
  assert.ok(block.includes('`git push`'), 'Must mention terminal git push');
  assert.ok(block.includes('`gh pr create`'), 'Must mention terminal gh pr create');
  assert.ok(block.includes('Human approval remains required for governed merges.'), 'Must state human approval rule');
  assert.ok(block.includes('<!-- SUTRA:END -->'), 'Must have closing delimiter');
});

test('SutraAgentInstructions component renders title and "Optional but recommended" badge', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(sutraComponent.SutraAgentInstructions, {})
  );

  assert.ok(html.includes('SUTRA Agent Instructions'), 'Must render component title');
  assert.ok(html.includes('Optional but recommended'), 'Must render "Optional but recommended" badge');
  assert.ok(html.includes('id=sutra-engineering-policy'), 'Must render block id');
  assert.ok(html.includes('v1'), 'Must render version 1');
});

test('SutraAgentInstructions component renders required explanatory copy', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(sutraComponent.SutraAgentInstructions, {})
  );

  assert.ok(
    html.includes('MCP makes SUTRA available to your coding agent.'),
    'Must explain MCP availability'
  );
  assert.ok(
    html.includes('we recommend adding the SUTRA instruction block to your existing'),
    'Must explain recommendation'
  );
  assert.ok(
    html.includes('If you already have an agent instruction file, add only the SUTRA block. Do not replace your existing instructions.'),
    'Must instruct not to replace existing instructions'
  );
  assert.ok(
    html.includes('Understanding MCP vs. Instruction Files'),
    'Must provide conceptual distinction'
  );
  assert.ok(
    html.includes('harness-level availability'),
    'Must explain harness-level availability'
  );
  assert.ok(
    html.includes('optional repository-level behavioral guidance'),
    'Must explain repository-level behavioral guidance'
  );
});

test('SutraAgentInstructions component renders accessible Copy button and targets', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(sutraComponent.SutraAgentInstructions, {})
  );

  assert.ok(html.includes('aria-label="Copy SUTRA agent instructions"'), 'Must have accessible copy aria-label');
  assert.ok(html.includes('title="Copy SUTRA agent instructions"'), 'Must have copy button title tooltip');
  assert.ok(html.includes('AGENTS.md'), 'Must display AGENTS.md target');
  assert.ok(html.includes('CLAUDE.md'), 'Must display CLAUDE.md target');
  assert.ok(html.includes('Cursor Rules'), 'Must display Cursor Rules target');
  assert.ok(html.includes('Recommended'), 'Must label AGENTS.md as recommended');
});

test('SutraAgentInstructions component does NOT leak secrets or credentials', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(sutraComponent.SutraAgentInstructions, {})
  );

  assert.strictEqual(html.includes('sutra_agent_'), false, 'Must not leak agent tokens');
  assert.strictEqual(html.includes('bearer '), false, 'Must not leak bearer tokens');
  assert.strictEqual(html.includes('password'), false, 'Must not leak passwords');
  assert.strictEqual(html.includes('client_secret'), false, 'Must not leak client secrets');
  assert.ok(html.includes('Contains zero credentials, secrets'), 'Must affirm safety');
});

test('Docs page sections include MCP Integration section', () => {
  const mcpSection = groupMcpModule.GroupMcpIntegration.find((s) => s.id === 'mcp-integration');
  assert.ok(mcpSection, 'Must export mcp-integration section');
  assert.strictEqual(mcpSection.category, 'MCP Integration');
  assert.ok(mcpSection.title.includes('MCP Integration'));

  const inData = docsDataModule.sections.find((s) => s.id === 'mcp-integration');
  assert.ok(inData, 'Must be registered in data.tsx sections array');

  const renderedSection = ReactDOMServer.renderToString(mcpSection.content);
  assert.ok(renderedSection.includes('SUTRA Agent Instructions'), 'Docs section must embed agent instructions');
  assert.ok(renderedSection.includes('Optional but recommended'), 'Docs section must display optional badge');
  assert.ok(renderedSection.includes('Engineering Boundary'), 'Docs section must describe boundary');
});
