'use client';
import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, UserRound, LogOut, Settings, ChevronDown, ExternalLink, X, Menu } from "lucide-react";
import { GitHubSyncButton } from "./GitHubSyncButton";
import { globalNav, repoNav } from "../lib/nav";
import { authService, User } from "../lib/auth";
import { I } from "../lib/icons";
import { SutraLoading } from "./sutra-loading";

function Mark(){
  return (
    <img
      src="/icon.png"
      alt="SUTRA Mark"
      className="mark"
      style={{
        width: 24,
        height: 24,
        objectFit: "contain",
        borderRadius: 4,
      }}
    />
  );
}

let _cachedUser: User | null = null;

export function ContentSkeleton() {
  return (
    <div style={{ padding: "24px 28px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
      <div style={{ marginBottom: 24 }}>
        <div className="skeleton" style={{ width: 120, height: 14, marginBottom: 8 }} />
        <div className="skeleton" style={{ width: 260, height: 28, marginBottom: 8 }} />
        <div className="skeleton" style={{ width: 400, height: 16 }} />
      </div>
      <div className="grid g4" style={{ marginBottom: 24 }}>
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="card" style={{ padding: 20 }}>
            <div className="skeleton" style={{ width: 80, height: 12, marginBottom: 12 }} />
            <div className="skeleton" style={{ width: 140, height: 28 }} />
          </div>
        ))}
      </div>
      <div className="card" style={{ padding: 24 }}>
        <div className="skeleton" style={{ width: 180, height: 20, marginBottom: 16 }} />
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="skeleton" style={{ width: "100%", height: 38 }} />
          <div className="skeleton" style={{ width: "100%", height: 38 }} />
          <div className="skeleton" style={{ width: "100%", height: 38 }} />
        </div>
      </div>
    </div>
  );
}

export function AppShell({children, isPublic = false}:{children:React.ReactNode, isPublic?: boolean}){
  const path = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(_cachedUser);
  const [loading, setLoading] = useState(!_cachedUser && !isPublic);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [path]);

  useEffect(() => {
    if (!authService.isAuthenticated()) {
      _cachedUser = null;
      setUser(null);
      setLoading(false);
      return;
    }
    
    authService.getCurrentUser()
      .then(u => {
        _cachedUser = u;
        setUser(u);
        setLoading(false);
      })
      .catch(() => {
        _cachedUser = null;
        setUser(null);
        setLoading(false);
      });
  }, [router, isPublic]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setDropdownOpen(false);
    _cachedUser = null;
    setUser(null);
    await authService.logout();
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        router.push("/search");
      }
      if (e.key === "Escape") setDropdownOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [router]);

  const repoMatch = path.match(/^\/repositories\/([^/]+)/);
  const repoName = repoMatch ? repoMatch[1] : null;
  const isRepoScope = Boolean(repoName);
  const isCodePage = Boolean(repoName && (path.endsWith("/code") || path.includes("/code/")));
  
  const currentNav = isRepoScope ? repoNav : globalNav;

  return <div className="shell">
    {/* Mobile drawer backdrop */}
    <div
      className={`sidebar-overlay ${mobileOpen ? "active" : ""}`}
      onClick={() => setMobileOpen(false)}
      aria-hidden="true"
    />

    <aside className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 4px 14px" }}>
        <Link href="/home" className="brand" style={{ padding: 0 }}><Mark/><span>SUTRA</span></Link>
        <button
          onClick={() => setMobileOpen(false)}
          className="mobile-close-btn"
          aria-label="Close navigation"
        >
          <X size={18} />
        </button>
      </div>
      
      {isRepoScope && (
        <div className="repo-scope-header" style={{ padding: "0 14px", marginBottom: 12 }}>
          <Link href="/repositories" className="repo-back-link" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--muted)", textDecoration: "none", marginBottom: 8 }}>
            <I.ChevronLeft size={13} />
            <span>All repositories</span>
          </Link>
          <div className="repo-card" style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", background: "rgba(255,255,255,0.03)", borderRadius: 6, border: "1px solid var(--line)" }}>
            <I.GitBranch size={15} className="cyan" />
            <span className="repo-card-name" style={{ fontSize: 13, fontWeight: 500 }}>{repoName}</span>
          </div>
        </div>
      )}

      {currentNav.map(group=><div key={group.label}>
        <div className="navlabel">{group.label}</div>
        {group.items.map(([href,label,Icon])=>{
          const actualHref = isRepoScope
            ? (href === "" ? `/repositories/${repoName}` : `/repositories/${repoName}${href}`)
            : href;
          const isRepoRoot = isRepoScope && (href === "" || actualHref === `/repositories/${repoName}`);
          const isHomeRoot = actualHref === "/home" || actualHref === "/";
          const isExactMatch = isRepoRoot || isHomeRoot;
          const active = isExactMatch
            ? path === actualHref
            : (path === actualHref || path.startsWith(actualHref + "/"));
          return <Link key={actualHref} href={actualHref} className={"navitem "+(active?"active":"")}>
            <Icon/><span>{label}</span>
          </Link>
        })}
      </div>)}
      <div className="sidebar-bottom">
        {user ? (
          <>
            <Link href="/profile" className="profile-mini">
              <div className="avatar">{user.username.slice(0, 2).toUpperCase()}</div><div><div className="mini-name">{user.username}</div><div className="mini-sub">View profile</div></div>
            </Link>
            <button
              onClick={handleLogout}
              title="Sign out"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: "6px 8px", borderRadius: 6, display: "flex", alignItems: "center" }}
            >
              <LogOut size={14} />
            </button>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%" }}>
            <Link
              href="/login"
              className="profile-mini"
              style={{
                justifyContent: "center",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid var(--border-default, #242424)",
                borderRadius: 6,
                padding: "8px",
                textDecoration: "none",
              }}
            >
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-bright, #f5f5f5)" }}>Sign in</span>
            </Link>
            <Link
              href="/register"
              className="profile-mini"
              style={{
                justifyContent: "center",
                background: "var(--accent-subtle, rgba(249, 115, 22, 0.12))",
                border: "1px solid rgba(249, 115, 22, 0.25)",
                borderRadius: 6,
                padding: "7px 8px",
                textDecoration: "none",
              }}
            >
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--accent, #f97316)" }}>Get Started</span>
            </Link>
          </div>
        )}
      </div>
    </aside>
    <main className="main">
      <header className="topbar">
        <div style={{ display: "flex", alignItems: "center", minWidth: 0 }}>
          <button
            className="mobile-menu-trigger"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation menu"
            title="Open navigation menu"
          >
            <Menu size={18} />
          </button>
          {(() => {
            if (isRepoScope && repoName) {
              const subPath = path.replace(`/repositories/${repoName}`, "").replace(/^\//, "");
              const section = subPath.split("/")[0] || "";
              const sectionNames: Record<string, string> = {
                "": "Overview",
                code: "Code",
                tasks: "Tasks",
                issues: "Issues",
                changes: "Changes",
                "pull-requests": "Pull Requests",
                ci: "CI / CD",
                agents: "Agents",
                "knowledge-graph": "Knowledge Graph",
                assistant: "AI Assistant",
                insights: "Insights",
                settings: "Settings",
                releases: "Releases",
                security: "Security",
              };
              const title = sectionNames[section] || (section ? section.replaceAll("-", " ") : "Overview");
              const hasSubId = subPath.split("/").length > 1;
              const subId = hasSubId ? subPath.split("/")[1] : null;

              return (
                <div className="crumb repo-crumb" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                  <Link href="/repositories" className="crumb-repo-root" style={{ color: "var(--muted)", textDecoration: "none" }}>Repositories</Link>
                  <span className="crumb-repo-root-sep" style={{ color: "var(--muted)" }}>/</span>
                  <Link href={`/repositories/${repoName}`} className="crumb-repo-name" style={{ color: section ? "var(--muted)" : "var(--fg)", textDecoration: "none", fontWeight: section ? 400 : 600 }}>
                    {repoName}
                  </Link>
                  {section && (
                    <>
                      <span style={{ color: "var(--muted)" }}>/</span>
                      {hasSubId ? (
                        <Link href={`/repositories/${repoName}/${section}`} className="crumb-repo-section" style={{ color: "var(--muted)", textDecoration: "none" }}>
                          {title}
                        </Link>
                      ) : (
                        <strong className="crumb-repo-section" style={{ color: "var(--fg)" }}>{title}</strong>
                      )}
                    </>
                  )}
                  {hasSubId && subId && (
                    <>
                      <span style={{ color: "var(--muted)" }}>/</span>
                      <strong style={{ color: "var(--fg)", fontFamily: "monospace", fontSize: 12 }}>#{subId.slice(0, 8)}</strong>
                    </>
                  )}
                </div>
              );
            }

            const globalTitles: Record<string, string> = {
              "/": "Overview",
              "/home": "Overview",
              "/tasks": "Tasks",
              "/my-work": "My Work",
              "/repositories": "Repositories",
              "/changes": "Changes",
              "/pull-requests": "Pull Requests",
              "/ci": "CI / CD",
              "/agents": "Agents",
              "/governance": "Governance & Policies",
              "/audit-log": "Audit",
              "/activity": "Activity",
              "/knowledge-graph": "Knowledge Graph",
              "/assistant": "Assistant",
              "/profile": "Profile",
              "/notifications": "Notifications",
              "/search": "Search",
              "/docs": "Documentation",
            };

            const segments = path.split("/").filter(Boolean);
            const rootRoute = `/${segments[0] || ""}`;
            const pageTitle = globalTitles[path] || globalTitles[rootRoute] || (segments[0]?.replaceAll("-", " ") || "Overview");
            const hasDetailId = segments.length > 1;
            const detailId = hasDetailId ? segments[1] : null;

            return (
              <div className="crumb" style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                <span>SUTRA</span>
                <span style={{ color: "var(--muted)" }}>/</span>
                {hasDetailId && detailId ? (
                  <>
                    <Link href={rootRoute} style={{ color: "var(--muted)", textDecoration: "none" }}>
                      {globalTitles[rootRoute] || segments[0]?.replaceAll("-", " ")}
                    </Link>
                    <span style={{ color: "var(--muted)" }}>/</span>
                    <strong style={{ color: "var(--fg)", fontFamily: "monospace", fontSize: 12 }}>#{detailId.slice(0, 8)}</strong>
                  </>
                ) : (
                  <strong style={{ color: "var(--fg)" }}>{pageTitle}</strong>
                )}
              </div>
            );
          })()}
        </div>
        <div className="top-actions">
          <button
            type="button"
            onClick={() => router.push("/search")}
            className="btn outline top-search-btn"
            title="Search repositories, tasks, pull requests, and changes (Ctrl+K)"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              fontSize: 12,
              height: 34,
              padding: "0 12px",
              color: "var(--muted)",
              background: "rgba(255,255,255,0.03)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              cursor: "pointer",
            }}
          >
            <I.Search size={14} />
            <span className="search-label">Search...</span>
            <kbd className="search-kbd" style={{
              fontSize: 10,
              background: "rgba(255,255,255,0.08)",
              padding: "1px 5px",
              borderRadius: 4,
              border: "1px solid var(--line)",
              marginLeft: 4,
            }}>
              ⌘K
            </kbd>
          </button>
          <div className="top-sync-wrapper">
            <GitHubSyncButton variant="compact" />
          </div>
          <Link
            href="/docs"
            className="btn guide top-docs-btn"
            title="Documentation & Guides"
            style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, height: 34 }}
          >
            <I.Book size={14} />
            <span>Docs</span>
          </Link>
          <Link href="/notifications" className="iconbtn" title="Notifications"><Bell size={15}/></Link>

          {/* Profile dropdown or Guest Auth actions */}
          {user ? (
            <div ref={dropdownRef} style={{ position: "relative" }}>
              <button
                className="iconbtn"
                title="Account"
                onClick={() => setDropdownOpen(o => !o)}
                style={{ display: "flex", alignItems: "center", gap: 4, paddingRight: 6 }}
              >
                <UserRound size={15}/>
                <ChevronDown size={11} style={{ opacity: 0.5, transition: "transform 200ms", transform: dropdownOpen ? "rotate(180deg)" : "none" }}/>
              </button>

              {dropdownOpen && (
                <div style={{
                  position: "absolute",
                  top: "calc(100% + 8px)",
                  right: 0,
                  minWidth: 200,
                  background: "var(--card, #151515)",
                  border: "1px solid var(--border-default, #242424)",
                  borderRadius: 10,
                  boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
                  overflow: "hidden",
                  zIndex: 9999,
                  animation: "fadeIn 120ms ease",
                }}>
                  <div style={{
                    padding: "12px 14px 10px",
                    borderBottom: "1px solid var(--border-default, #242424)",
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-bright, #f5f5f5)" }}>{user.username}</div>
                    <div style={{ fontSize: 11, color: "var(--muted, #8a8a8a)", marginTop: 2 }}>{(user as any).email}</div>
                  </div>

                  <div style={{ padding: "6px 0" }}>
                    <Link
                      href="/profile"
                      onClick={() => setDropdownOpen(false)}
                      style={{
                        display: "flex", alignItems: "center", gap: 10,
                        padding: "8px 14px", fontSize: 13, color: "var(--text-bright, #f5f5f5)",
                        textDecoration: "none", transition: "background 120ms",
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >
                      <UserRound size={14} style={{ opacity: 0.6 }} />
                      Profile
                    </Link>

                    <div style={{ height: 1, background: "var(--border-default, #242424)", margin: "6px 0" }} />

                    <button
                      onClick={handleLogout}
                      style={{
                        display: "flex", alignItems: "center", gap: 10, width: "100%",
                        padding: "8px 14px", fontSize: 13, color: "#ef4444",
                        background: "none", border: "none", cursor: "pointer",
                        textAlign: "left", transition: "background 120ms",
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = "rgba(239,68,68,0.08)")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >
                      <LogOut size={14} style={{ opacity: 0.8 }} />
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Link
                href="/login"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "5px 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  color: "var(--text-bright, #f5f5f5)",
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid var(--border-default, #242424)",
                  textDecoration: "none",
                  transition: "all 120ms ease",
                }}
              >
                Sign in
              </Link>
              <Link
                href="/register"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "5px 12px",
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#0b0b0b",
                  background: "var(--accent, #f97316)",
                  border: "none",
                  textDecoration: "none",
                  transition: "all 120ms ease",
                }}
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </header>
      <div className={`content ${isCodePage ? "content-fullbleed" : ""}`} style={{ flex: 1 }}>{loading ? <ContentSkeleton /> : children}</div>
      {!isCodePage && (
        <footer
          style={{
            borderTop: "1px solid var(--line)",
            background: "var(--surface)",
            padding: "18px 28px",
            marginTop: "auto",
            fontSize: 12,
            color: "var(--muted)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>© {new Date().getFullYear()} SUTRA. A Sudarshan Harness Product. All rights reserved.</div>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span>Contact us at <a href="mailto:sutra@sudarshanai.com" style={{ color: "#60A5FA", textDecoration: "none" }}>sutra@sudarshanai.com</a></span>
            <span>•</span>
            <span>AI-Native Engineering Control Plane</span>
          </div>
        </footer>
      )}
    </main>
  </div>
}


export function PageHead({eyebrow,title,sub,action}:{eyebrow?:string,title:string,sub?:string,action?:React.ReactNode}){
 return <div className="page-head"><div>{eyebrow&&<div className="eyebrow">{eyebrow}</div>}<h1 className="h1">{title}</h1>{sub&&<div className="sub" style={{marginTop:7}}>{sub}</div>}</div>{action&&<div className="actions">{action}</div>}</div>
}
export function Btn({ children, primary = false, violet = false, sm = false, className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean, violet?: boolean, sm?: boolean }) {
  return (
    <button 
      className={`btn ${primary ? "primary " : ""}${violet ? "violet " : ""}${sm ? "sm " : ""}${className}`.trim()} 
      {...props}
    >
      {children}
    </button>
  );
}
export function Card({children,className="",style}:{children:React.ReactNode,className?:string,style?:React.CSSProperties}){return <div className={"card "+className} style={style}>{children}</div>}
export function Badge({children, tone="", ...props}: {children: React.ReactNode, tone?: string} & React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={"badge " + tone} {...props}>{children}</span>
}
export function Pipeline({compact=false}:{compact?:boolean}){
 const steps=["Repository","Task","Agent","Change","Review","Ship"];
 return <div className={"pipeline "+(compact?"":"")} >{steps.map((x,i)=><div className="pipe" key={x}><div className="node"><span className="dot"></span><span>{x}</span></div>{i<steps.length-1&&<span className="arrow"/>}</div>)}</div>
}
export function Stat({label,value,delta}:{label:string,value:string,delta?:string}){return <Card><div className="stat"><div className="eyebrow">{label}</div><div className="num">{value}</div>{delta&&<div className="delta">{delta}</div>}</div></Card>}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon && <div className="empty-state-icon">{icon}</div>}
      <div className="empty-state-title">{title}</div>
      {description && <div className="empty-state-desc">{description}</div>}
      {action && <div>{action}</div>}
    </div>
  );
}

export function Table({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className="table-container">
      <table className={"table " + className}>{children}</table>
    </div>
  );
}

export { SutraLoading } from "./sutra-loading";
export {
  Skeleton,
  SkeletonFileTree,
  SkeletonCodeViewer,
  SkeletonCommitList,
  SkeletonPRList,
  SkeletonIssueList,
  SkeletonChangeList,
  SkeletonAgentList,
  SkeletonCIRuns,
  SkeletonRepoOverview,
  SkeletonRepoSettings,
} from "./skeleton";

