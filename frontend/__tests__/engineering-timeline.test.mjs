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
    if (id.startsWith('@/lib/')) {
      const resolved = path.resolve(process.cwd(), id.replace('@/', ''));
      if (fs.existsSync(resolved + '.ts')) return loadTsxModule(id.replace('@/', '') + '.ts');
      if (fs.existsSync(resolved + '.tsx')) return loadTsxModule(id.replace('@/', '') + '.tsx');
    }
    if (id.startsWith('@/components/')) {
      const resolved = path.resolve(process.cwd(), id.replace('@/', ''));
      if (fs.existsSync(resolved + '.tsx')) return loadTsxModule(id.replace('@/', '') + '.tsx');
      if (fs.existsSync(resolved + '.ts')) return loadTsxModule(id.replace('@/', '') + '.ts');
    }
    if (id.startsWith('.')) {
      const resolved = path.resolve(path.dirname(fullPath), id);
      if (fs.existsSync(resolved + '.tsx')) return loadTsxModule(path.relative(process.cwd(), resolved + '.tsx'));
      if (fs.existsSync(resolved + '.ts')) return loadTsxModule(path.relative(process.cwd(), resolved + '.ts'));
      if (fs.existsSync(resolved)) return loadTsxModule(path.relative(process.cwd(), resolved));
    }
    if (id === 'next/link') {
      const LinkComp = ({ children, href, ...props }) => React.createElement('a', { href, ...props }, children);
      return { default: LinkComp, __esModule: true };
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

const { EngineeringTimeline } = loadTsxModule('components/EngineeringTimeline.tsx');

const mockActiveLifecycleData = {
  current_stage: "AWAITING_HUMAN_APPROVAL",
  overall_state: "AWAITING_HUMAN_APPROVAL",
  next_action: "human_approve",
  next_actor: "HUMAN",
  blocked_reasons: ["Independent human review required before merge."],
  task: {
    id: "task_12345678abcdef",
    status: "in_progress",
    title: "Implement secure auth module",
    priority: "high",
    assigned_agent_id: "agent_abc",
    claimed_by_session_id: "session_xyz",
  },
  session: {
    id: "session_xyz",
    agent_id: "agent_abc",
    status: "active",
    lease_expires_at: "2026-09-12T15:00:00Z",
  },
  change: {
    id: "change_98765432",
    status: "proposed",
    commit_sha: "a1b2c3d4e5f6",
    base_commit: "000000000000",
    branch: "agent/task-auth",
    intent: "Implement secure auth module",
  },
  pull_request: {
    id: "pr_55554444",
    status: "open",
    title: "feat(auth): implement secure auth",
    source_branch: "agent/task-auth",
    target_branch: "main",
    source_commit: "a1b2c3d4e5f6",
    target_commit: null,
    merged_at: null,
    merged_by: null,
  },
  ci: {
    status: "passed",
    summary: { total: 3, passed: 3, failed: 0, pending: 0 },
    checks: [
      { id: "c1", name: "Security Audit", status: "completed", conclusion: "success" },
      { id: "c2", name: "Test Suite", status: "completed", conclusion: "success" },
    ],
  },
  governance: {
    verdict: "READY_FOR_APPROVAL",
    passed: true,
    blocking_reasons: [],
  },
  approval: {
    is_approved: false,
    required_approvals: 1,
    current_approvals: 0,
    approved_by: [],
    head_changed_after_approval: false,
  },
  merge: {
    is_merged: false,
    can_merge: false,
    blocking_reasons: ["Awaiting independent human reviewer approval."],
    merge_commit_sha: null,
  },
  task_completion: {
    is_completed: false,
    completed_at: null,
  },
  timeline: [
    {
      stage: "task_created",
      label: "Task Created",
      status: "completed",
      timestamp: "2026-09-12T12:00:00Z",
      actor_type: "human",
      actor_id: "user_owner",
      details: {},
    },
    {
      stage: "task_claimed",
      label: "Task Claimed & Session Locked",
      status: "completed",
      timestamp: "2026-09-12T12:01:00Z",
      actor_type: "agent",
      actor_id: "agent_abc",
      details: {},
    },
    {
      stage: "work_submitted",
      label: "Work Submitted & Reconciled",
      status: "completed",
      timestamp: "2026-09-12T12:05:00Z",
      actor_type: "agent",
      actor_id: "agent_abc",
      details: {},
    },
    {
      stage: "pull_request_opened",
      label: "Substrate Pull Request Opened",
      status: "completed",
      timestamp: "2026-09-12T12:05:30Z",
      actor_type: "system",
      actor_id: "sutra_substrate",
      details: {},
    },
    {
      stage: "ci_evaluating",
      label: "Automated CI & Validation Gates",
      status: "completed",
      timestamp: "2026-09-12T12:06:30Z",
      actor_type: "system",
      actor_id: "sutra_ci",
      details: {},
    },
    {
      stage: "awaiting_human_approval",
      label: "Independent Human Review & Approval",
      status: "active",
      timestamp: null,
      actor_type: "human",
      actor_id: null,
      details: {},
    },
    {
      stage: "ready_for_merge",
      label: "Governed Substrate Merge",
      status: "pending",
      timestamp: null,
      actor_type: "human",
      actor_id: null,
      details: {},
    },
    {
      stage: "task_completed",
      label: "Task Completed & Provenance Sealed",
      status: "pending",
      timestamp: null,
      actor_type: "system",
      actor_id: null,
      details: {},
    },
  ],
};

test('EngineeringTimeline renders with canonical data and header', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(EngineeringTimeline, {
      initialData: mockActiveLifecycleData,
      pollingIntervalMs: 0,
    })
  );

  assert.ok(html.includes('Authoritative Engineering Lifecycle'), 'Must display title');
  assert.ok(html.includes('Current State: AWAITING HUMAN APPROVAL'), 'Must display current overall state');
  assert.ok(html.includes('Next Actor: HUMAN'), 'Must designate next actor as HUMAN');
});

test('EngineeringTimeline displays canonical milestones and actor badges', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(EngineeringTimeline, {
      initialData: mockActiveLifecycleData,
      pollingIntervalMs: 0,
    })
  );

  assert.ok(html.includes('Task Created'), 'Must render Task Created stage');
  assert.ok(html.includes('Task Claimed &amp; Session Locked'), 'Must render Task Claimed stage');
  assert.ok(html.includes('Work Submitted &amp; Reconciled'), 'Must render Work Submitted stage');
  assert.ok(html.includes('Substrate Pull Request Opened'), 'Must render PR Opened stage');
  assert.ok(html.includes('Automated CI &amp; Validation Gates'), 'Must render CI Gates stage');
  assert.ok(html.includes('Independent Human Review &amp; Approval'), 'Must render Human Review stage');
  assert.ok(html.includes('Governed Substrate Merge'), 'Must render Governed Merge stage');

  assert.ok(html.includes('Human Authority'), 'Must render Human Authority badge');
  assert.ok(html.includes('Autonomous Agent'), 'Must render Autonomous Agent badge');
  assert.ok(html.includes('SUTRA Governance'), 'Must render SUTRA Governance badge');
});

test('EngineeringTimeline renders active blockers when present', () => {
  const html = ReactDOMServer.renderToString(
    React.createElement(EngineeringTimeline, {
      initialData: mockActiveLifecycleData,
      pollingIntervalMs: 0,
    })
  );

  assert.ok(html.includes('Active Lifecycle Blockers'), 'Must render blockers alert');
  assert.ok(html.includes('Independent human review required before merge.'), 'Must list the blocker text');
});

test('EngineeringTimeline completed state displays completion banner', () => {
  const completedData = {
    ...mockActiveLifecycleData,
    overall_state: 'COMPLETED',
    current_stage: 'TASK_COMPLETED',
    next_actor: 'NONE',
    next_action: 'none',
    blocked_reasons: [],
  };

  const html = ReactDOMServer.renderToString(
    React.createElement(EngineeringTimeline, {
      initialData: completedData,
      pollingIntervalMs: 0,
    })
  );

  assert.ok(html.includes('Current State: COMPLETED'), 'Must show COMPLETED state');
  assert.ok(html.includes('All gates satisfied'), 'Must show all gates satisfied banner');
  assert.strictEqual(html.includes('Active Lifecycle Blockers'), false, 'Must not show blockers when none');
});
