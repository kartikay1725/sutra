/**
 * Canonical Source of Truth for SUTRA Agent Instructions.
 *
 * This module defines the canonical version and markdown content for the
 * repository-level SUTRA agent instruction block (e.g. AGENTS.md, CLAUDE.md, .cursorrules).
 *
 * IMPORTANT:
 * - MCP provides harness-level availability of SUTRA.
 * - This repository instruction block provides optional, repository-level behavioral guidance
 *   that helps coding agents consistently choose SUTRA for governed engineering.
 * - SUTRA operates fully over MCP without requiring repository instruction files.
 * - Do NOT duplicate this instruction text independently; always import from this module.
 */

export const SUTRA_INSTRUCTION_BLOCK_ID = 'sutra-engineering-policy';
export const SUTRA_INSTRUCTION_VERSION = 1;

export const SUTRA_RECOMMENDED_FILE = 'AGENTS.md';

export const SUTRA_SUPPORTED_TARGETS = [
  {
    name: 'AGENTS.md',
    recommended: true,
    description: 'Cross-agent standard instruction file placed in repository root.',
    path: 'AGENTS.md',
  },
  {
    name: 'CLAUDE.md',
    recommended: false,
    description: 'Anthropic Claude Code and desktop agent project memory file.',
    path: 'CLAUDE.md',
  },
  {
    name: 'Cursor Rules',
    recommended: false,
    description: 'Cursor IDE agent instructions (.cursorrules or .cursor/rules/*).',
    path: '.cursorrules',
  },
  {
    name: 'Equivalent Instruction Files',
    recommended: false,
    description: 'Any workspace instructions file recognized by your agent harness.',
    path: 'Custom',
  },
] as const;

export const SUTRA_CANONICAL_INSTRUCTION_BLOCK = `<!-- SUTRA:START id=sutra-engineering-policy version=1 -->

## SUTRA Engineering Control

SUTRA is the engineering control plane for this repository.

For repository engineering tasks, use the available \`sutra_*\` tools for
SUTRA-governed changes, commits, pull requests, CI/governance, and merge requests.

When a user gives a new engineering request and no existing SUTRA task is specified,
create the SUTRA Task from the user's request using \`sutra_start_task\`.
Do not ask the user for a SUTRA Task ID unless they explicitly refer to an existing task.

Use:
- \`sutra_declare_change\` for governed change declaration
- \`sutra_push_commit\` for governed commits/push operations
- \`sutra_open_pull_request\` for pull request creation
- \`sutra_get_status\` for lifecycle status
- \`sutra_get_provenance\` for provenance
- \`sutra_get_governance\` for governance state
- \`sutra_complete_task\` to record the final execution/validation summary

Terminal tools are appropriate for reading/editing files, running tests,
running local builds, and repository inspection.

For governed engineering work, do not use terminal:
- \`git commit\`
- \`git push\`
- \`gh pr create\`

Human approval remains required for governed merges.

<!-- SUTRA:END -->`;
