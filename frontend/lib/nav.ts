import { I } from "./icons";

export const globalNav = [
  {label:"Workspace", items:[
    ["/home","Home",I.Home],[ "/my-work","My Work",I.BriefcaseBusiness],
    ["/repositories","Repositories",I.Box],["/agents","Agents",I.Bot],["/docs","Documentation",I.Book],[ "/notifications","Notifications",I.Bell],
  ]},
  // {label:"Organization", items:[
  //   ["/organizations","Organizations",I.Users],[ "/governance","Governance",I.ShieldCheck],
  //   ["/audit-log","Audit Log",I.History],[ "/marketplace","Marketplace",I.Layers3]
  // ]}
] as const;

export const repoNav = [
  {label:"Repository", items:[
    ["/code","Code",I.FileCode2],["/issues","Issues",I.CircleDot],["/tasks","Tasks",I.ListTodo],
    ["/discussions","Discussions",I.MessageSquare]
  ]},
  {label:"Engineering", items:[
    ["/changes","Changes",I.GitBranch],[ "/pull-requests","Pull Requests",I.GitPullRequest],
    ["/agents","Agents",I.Bot],[ "/ci","CI / Pipelines",I.Workflow]
  ]},
  {label:"Intelligence", items:[
    ["/knowledge-graph","Knowledge Graph",I.Network],[ "/insights","Insights",I.Activity],[ "/assistant","AI Assistant",I.Sparkles]
  ]},
  {label:"Settings", items:[
    ["/settings","Repository Settings",I.Settings]
  ]}
] as const;
