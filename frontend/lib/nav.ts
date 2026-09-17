import { I } from "./icons";

export const globalNav = [
  {
    label: "Workspace",
    items: [
      ["/home", "Overview", I.LayoutDashboard],
      ["/tasks", "Tasks", I.ListTodo],
      ["/my-work", "My Work", I.CheckSquare],
    ],
  },
  {
    label: "Engineering",
    items: [
      ["/repositories", "Repositories", I.Box],
      ["/agents", "Agents", I.Bot],
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
      ["/agents", "Agents", I.Bot],
    ],
  },
  {
    label: "Intelligence",
    items: [
      ["/knowledge-graph", "Knowledge Graph", I.Network],
      ["/assistant", "AI Assistant", I.Sparkles],
    ],
  },
  {
    label: "Settings",
    items: [
      ["/settings", "Repository Settings", I.Settings],
    ],
  },
] as const;

