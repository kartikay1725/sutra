"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";
import { authService, User } from "@/lib/auth";
import {
  Home,
  Compass,
  FolderGit2,
  ListTodo,
  GitPullRequest,
  GitBranch,
  Bot,
  PlaySquare,
  Bell,
  Settings,
  UserRound,
  Activity,
  ShieldCheck,
  Package,
  LayoutDashboard,
  Code2,
  CircleDot,
  MessageSquare,
  Rocket,
  ChevronLeft,
  Sliders,
  Network,
  LogOut,
  Search,
} from "lucide-react";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (pathname === '/login' || pathname === '/signup') return;
    
    if (!authService.isAuthenticated()) {
      router.push('/login');
      return;
    }

    authService.getCurrentUser()
      .then(u => setUser(u))
      .catch(() => router.push('/login'));
  }, [pathname, router]);

  const handleLogout = async () => {
    await authService.logout();
    router.push('/login');
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        router.push("/search");
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [router]);

  // Match /repositories/[name] or any sub-route under it
  const repoMatch = pathname.match(/^\/repositories\/([^/]+)/);
  const repoName = repoMatch ? repoMatch[1] : null;
  const isRepoScope = Boolean(repoName);

  // Global Workspace Navigation
  const globalWorkspaceNav = [
    { label: "Home", href: "/", icon: Home },
    { label: "My Work", href: "/my-work", icon: ListTodo },
    { label: "Repositories", href: "/repositories", icon: FolderGit2 },
    { label: "Agents", href: "/agents", icon: Bot },
    { label: "Intelligence", href: "/intelligence", icon: Activity },
  ];

  const globalNetworkNav = [
    { label: "Notifications", href: "/notifications", icon: Bell },
    { label: "Profile", href: "/profile", icon: UserRound },
  ];

  // Repository-Scoped Navigation
  const repoBase = `/repositories/${repoName}`;
  const repoNav = [
    { label: "Overview", href: repoBase, icon: LayoutDashboard, exact: true },
    { label: "Code", href: `${repoBase}/code`, icon: Code2 },
    { label: "Issues", href: `${repoBase}/issues`, icon: CircleDot },
    { label: "Tasks", href: `${repoBase}/tasks`, icon: ListTodo },
    { label: "Changes", href: `${repoBase}/changes`, icon: GitBranch },
    { label: "Pull Requests", href: `${repoBase}/pull-requests`, icon: GitPullRequest },
  ];

  const repoEngineeringNav = [
    { label: "Agents", href: `${repoBase}/agents`, icon: Bot },
    { label: "CI / CD", href: `${repoBase}/ci`, icon: PlaySquare },
    { label: "Security", href: `${repoBase}/security`, icon: ShieldCheck },
  ];

  const repoIntelligenceNav = [
    { label: "AI Assistant", href: `${repoBase}/assistant`, icon: Bot },
    { label: "Knowledge Graph", href: `${repoBase}/knowledge-graph`, icon: Network },
  ];

  const repoDeliveryNav = [
    { label: "Releases", href: `${repoBase}/releases`, icon: Package },
    // { label: "Deployments", href: `${repoBase}/deployments`, icon: Rocket },
  ];

  const repoSettingsNav = [
    { label: "Repository Settings", href: `${repoBase}/settings`, icon: Sliders },
  ];

  const isNavActive = (href: string, exact: boolean = false) => {
    if (exact) {
      return pathname === href;
    }
    if (href === "/") {
      return pathname === "/";
    }
    return pathname === href || pathname.startsWith(href + "/");
  };

  const getBreadcrumbTitle = () => {
    if (isRepoScope) {
      const sub = pathname.replace(repoBase, "");
      if (!sub || sub === "/") return `${repoName} / Overview`;
      const cleanSub = sub.replace(/^\//, "").split("/")[0];
      const titleMap: Record<string, string> = {
        code: "Code",
        issues: "Issues",
        tasks: "Tasks",
        changes: "Changes",
        "pull-requests": "Pull Requests",
        agents: "Agents",
        ci: "CI / CD",
        security: "Security",
        releases: "Releases",
        deployments: "Deployments",
        insights: "Insights",
        assistant: "AI Assistant",
        "knowledge-graph": "Knowledge Graph",
        settings: "Repository Settings",
      };
      return `${repoName} / ${titleMap[cleanSub] || cleanSub}`;
    }

    if (pathname === "/") return "Home";
    if (pathname === "/my-work") return "My Work";
    if (pathname === "/explore") return "Explore";
    if (pathname === "/repositories") return "Repositories";
    if (pathname === "/activity") return "Activity";
    if (pathname === "/agents") return "Agents Gateway";
    if (pathname === "/notifications") return "Notifications";
    if (pathname === "/profile") return "Profile";
    return "Engineering workspace";
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Link href="/" className="brand-link">
            <div className="mark" />
            <span>SUTRA</span>
          </Link>
        </div>

        {isRepoScope ? (
          /* REPOSITORY SCOPED SIDEBAR */
          <>
            <div className="repo-scope-header">
              <Link href="/repositories" className="repo-back-link">
                <ChevronLeft size={13} />
                <span>All repositories</span>
              </Link>
              <div className="repo-card">
                <GitBranch size={15} className="cyan" />
                <span className="repo-card-name">{repoName}</span>
                <span className="badge cyan repo-badge">Repo</span>
              </div>
            </div>

            <nav className="side-nav">
              <div className="navgroup">
                <div className="navtitle">Repository</div>
                {repoNav.map((item) => {
                  const Icon = item.icon;
                  const active = isNavActive(item.href, item.exact);
                  return (
                    <Link
                      key={item.label}
                      href={item.href}
                      className={`navitem ${active ? "active" : ""}`}
                    >
                      <Icon size={16} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>

              <div className="navgroup">
                <div className="navtitle">Intelligence</div>
                {repoIntelligenceNav.map((item) => {
                  const Icon = item.icon;
                  const active = isNavActive(item.href);
                  return (
                    <Link
                      key={item.label}
                      href={item.href}
                      className={`navitem ${active ? "active" : ""}`}
                    >
                      <Icon size={16} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>

              <div className="navgroup">
                <div className="navtitle">Engineering</div>
                {repoEngineeringNav.map((item) => {
                  const Icon = item.icon;
                  const active = isNavActive(item.href);
                  return (
                    <Link
                      key={item.label}
                      href={item.href}
                      className={`navitem ${active ? "active" : ""}`}
                    >
                      <Icon size={16} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>

              <div className="navgroup">
                <div className="navtitle">Delivery</div>
                {repoDeliveryNav.map((item) => {
                  const Icon = item.icon;
                  const active = isNavActive(item.href);
                  return (
                    <Link
                      key={item.label}
                      href={item.href}
                      className={`navitem ${active ? "active" : ""}`}
                    >
                      <Icon size={16} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </nav>

            <div className="sidebottom">
              {repoSettingsNav.map((item) => {
                const Icon = item.icon;
                const active = isNavActive(item.href);
                return (
                  <Link
                    key={item.label}
                    href={item.href}
                    className={`navitem ${active ? "active" : ""}`}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </>
        ) : (
          /* GLOBAL WORKSPACE SIDEBAR */
          <>
            <div className="workspace">
              <small>Workspace</small>
              <strong>{user ? `${user.username}'s space` : "Loading..."}</strong>
              <div className="muted" style={{ fontSize: 10, marginTop: 3 }}>
                {/* Repository count goes here */}
              </div>
            </div>

            <nav className="side-nav">
              <div className="navgroup">
                <div className="navtitle">Workspace</div>
                {globalWorkspaceNav.map((item) => {
                  const Icon = item.icon;
                  const active = isNavActive(item.href, item.href === "/");
                  return (
                    <Link
                      key={item.label}
                      href={item.href}
                      className={`navitem ${active ? "active" : ""}`}
                    >
                      <Icon size={16} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>

              <div className="navgroup">
                <div className="navtitle">Network</div>
                {globalNetworkNav.map((item) => {
                  const Icon = item.icon;
                  const active = isNavActive(item.href);
                  return (
                    <Link
                      key={item.label}
                      href={item.href}
                      className={`navitem ${active ? "active" : ""}`}
                    >
                      <Icon size={16} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </nav>
          </>
        )}
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="crumb">
            <span className="mobileonly">SUTRA</span>
            <span className="mobileonly">/</span>
            <span className="muted">SUTRA</span>
            <span className="muted">/</span>
            <strong>{getBreadcrumbTitle()}</strong>
          </div>
          <div className="topactions" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              className="searchbox"
              style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8, padding: "0 10px", width: 200, height: 34 }}
              onClick={() => router.push("/search")}
            >
              <Search size={14} />
              <span>Search...</span>
              <span style={{ marginLeft: "auto", fontSize: 10, opacity: 0.6 }}>⌘K</span>
            </div>
            <Link href="/notifications" className="iconbtn" title="Notifications">
              <Bell size={15} />
            </Link>
            <Link href="/profile" className="avatar" title="View Profile">
              {user ? user.username.substring(0, 2).toUpperCase() : "??"}
            </Link>
            <button
              onClick={handleLogout}
              className="iconbtn"
              title="Sign out"
              style={{ cursor: "pointer", background: "none", border: "none", color: "var(--muted)" }}
            >
              <LogOut size={15} />
            </button>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
