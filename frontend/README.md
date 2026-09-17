# SUTRA Frontend

A premium, dark developer-platform frontend for SUTRA — the engineering OS for autonomous agents.

## Included

- Next.js App Router + TypeScript
- 36 mapped screens/routes from the SUTRA screen map
- Responsive desktop/tablet/mobile layouts
- Reusable shell, pipeline, cards, badges, stats, tables, traces, code/diff surfaces
- Original SUTRA visual language: deep navy, cyan/aqua glow, restrained violet gradients
- Mock data only; frontend is intentionally backend-independent
- Reference image included at `public/sutra-reference.png`

## Run

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Main routes

Auth: `/login`, `/signup`

Workspace: `/home`, `/my-work`, `/explore`, `/repositories`, `/notifications`

Repository: `/repositories/sutra-core`, `/repositories/sutra-core/code`, `/repositories/sutra-core/issues`, `/repositories/sutra-core/tasks`, `/repositories/sutra-core/discussions`, `/repositories/sutra-core/settings`, `/repositories/new`

Workflow: `/changes`, `/changes/482`, `/pull-requests`, `/pull-requests/91`

Agents: `/agents`, `/agents/1`, `/agents/1/runs/8831`, `/repo-agents`, `/assistant`

Delivery: `/ci`, `/ci/1200`, `/environments`, `/deployments`

Intelligence: `/knowledge-graph`, `/insights`

Network: `/profile`, `/organizations`, `/governance`, `/audit-log`, `/marketplace`

Account: `/search`

The root `/` is a polished marketing/landing page matching the provided SUTRA reference direction.
