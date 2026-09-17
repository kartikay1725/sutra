import { I } from "./icons";

export const globalNav = [
  {
    label: "Workspace",
    items: [
      ["/home", "Overview", I.LayoutDashboard],
      ["/my-work", "My Work", I.CheckSquare],
      ["/tasks", "Tasks", I.ListTodo],
    ],
  },
  {
    label: "Engineering",
    items: [
      ["/repositories", "Repositories", I.Box],
      ["/changes", "Changes", I.GitBranch],
      ["/agents", "Agents", I.Cpu],
      ["/audit-log", "Audit Log", I.ScrollText],
    ],
  },
] as const;

export const repoNav = [
  {
    label: "Repository",
    items: [
      ["", "Overview", I.LayoutDashboard],
      ["/code", "Code", I.FileCode2],
      ["/tasks", "Tasks", I.ListTodo],
      ["/issues", "Issues", I.CircleDot],
    ],
  },
  {
    label: "Engineering",
    items: [
      ["/changes", "Changes", I.GitBranch],
      ["/pull-requests", "Pull Requests", I.GitPullRequest],
      ["/ci", "CI / CD", I.Workflow],
      ["/agents", "Agents", I.Cpu],
    ],
  },
  {
    label: "Investigation",
    items: [
      ["/knowledge-graph", "Knowledge Graph", I.Network],
      ["/assistant", "Assistant", I.Terminal],
    ],
  },
  {
    label: "Settings",
    items: [
      ["/settings", "Repository Settings", I.Settings],
    ],
  },
] as const;

