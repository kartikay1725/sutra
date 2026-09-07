'use client';
import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, UserRound, LogOut, Settings, ChevronDown } from "lucide-react";
import { globalNav, repoNav } from "../lib/nav";
import { authService, User } from "../lib/auth";
import { I } from "../lib/icons";

function Mark(){ return <div className="mark" aria-label="SUTRA mark" /> }

export function AppShell({children, isPublic = false}:{children:React.ReactNode, isPublic?: boolean}){
  const path = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!authService.isAuthenticated()) {
      if (isPublic) {
        setLoading(false);
      } else {
        router.push("/login");
      }
      return;
    }
    
    authService.getCurrentUser()
      .then(u => {
        setUser(u);
        setLoading(false);
      })
      .catch(() => {
        authService.logout();
        if (isPublic) {
          setLoading(false);
        } else {
          router.push("/login");
        }
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
    await authService.logout();
    router.push("/login");
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

  if (loading) {
    return <div className="shell" style={{ display: "grid", placeItems: "center" }}><div className="muted">Loading SUTRA...</div></div>;
  }

  const repoMatch = path.match(/^\/repositories\/([^/]+)/);
  const repoName = repoMatch ? repoMatch[1] : null;
  const isRepoScope = Boolean(repoName);
  
  const currentNav = isRepoScope ? repoNav : globalNav;

  return <div className="shell">
    <aside className="sidebar">
      <Link href="/home" className="brand"><Mark/><span>SUTRA</span></Link>
      
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
          const isGlobalGroup = (group.label as string) === "Workspace" || (group.label as string) === "Organization";
          const actualHref = isRepoScope && !isGlobalGroup ? `/repositories/${repoName}${href}` : href;
          const active = path===actualHref || (actualHref!=="/home" && path.startsWith(actualHref));
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
          <Link href="/login" className="profile-mini" style={{ justifyContent: "center", background: "rgba(255,255,255,0.05)", borderRadius: 6, padding: "8px", textDecoration: "none" }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)" }}>Sign in</span>
          </Link>
        )}
      </div>
    </aside>
    <main className="main">
      <header className="topbar">
        <div className="crumb"><span>SUTRA</span><span>/</span><strong>{path === "/home" ? "Home" : path.split("/").filter(Boolean).slice(-1)[0]?.replaceAll("-"," ")}</strong></div>
        <div className="top-actions">
          <Link
            href="/docs"
            className="btn guide"
            title="Documentation & Guides"
            style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, height: 34 }}
          >
            <I.Book size={14} />
            <span>Docs</span>
          </Link>
          <Link href="/notifications" className="iconbtn" title="Notifications"><Bell size={15}/></Link>

          {/* Profile dropdown */}
          <div ref={dropdownRef} style={{ position: "relative" }}>
            <button
              className="iconbtn"
              title="Account"
              onClick={() => setDropdownOpen(o => !o)}
              style={{ display: "flex", alignItems: "center", gap: 4, paddingRight: user ? 6 : undefined }}
            >
              <UserRound size={15}/>
              {user && <ChevronDown size={11} style={{ opacity: 0.5, transition: "transform 200ms", transform: dropdownOpen ? "rotate(180deg)" : "none" }}/>}
            </button>

            {dropdownOpen && (
              <div style={{
                position: "absolute",
                top: "calc(100% + 8px)",
                right: 0,
                minWidth: 200,
                background: "var(--card)",
                border: "1px solid var(--line)",
                borderRadius: 10,
                boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
                overflow: "hidden",
                zIndex: 9999,
                animation: "fadeIn 120ms ease",
              }}>
                {user && (
                  <div style={{
                    padding: "12px 14px 10px",
                    borderBottom: "1px solid var(--line)",
                  }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{user.username}</div>
                    <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{(user as any).email}</div>
                  </div>
                )}

                <div style={{ padding: "6px 0" }}>
                  <Link
                    href="/profile"
                    onClick={() => setDropdownOpen(false)}
                    style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "8px 14px", fontSize: 13, color: "var(--fg)",
                      textDecoration: "none", transition: "background 120ms",
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    <UserRound size={14} style={{ opacity: 0.6 }} />
                    Profile
                  </Link>

                  <Link
                    href="/settings"
                    onClick={() => setDropdownOpen(false)}
                    style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "8px 14px", fontSize: 13, color: "var(--fg)",
                      textDecoration: "none", transition: "background 120ms",
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    <Settings size={14} style={{ opacity: 0.6 }} />
                    Settings
                  </Link>

                  <div style={{ height: 1, background: "var(--line)", margin: "6px 0" }} />

                  <button
                    onClick={handleLogout}
                    style={{
                      display: "flex", alignItems: "center", gap: 10, width: "100%",
                      padding: "8px 14px", fontSize: 13, color: "#ff8fa0",
                      background: "none", border: "none", cursor: "pointer",
                      textAlign: "left", transition: "background 120ms",
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,143,160,0.07)")}
                    onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  >
                    <LogOut size={14} style={{ opacity: 0.7 }} />
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>
      <div className="content">{children}</div>
    </main>
  </div>
}


export function PageHead({eyebrow,title,sub,action}:{eyebrow?:string,title:string,sub?:string,action?:React.ReactNode}){
 return <div className="page-head"><div>{eyebrow&&<div className="eyebrow">{eyebrow}</div>}<h1 className="h1">{title}</h1>{sub&&<div className="sub" style={{marginTop:7}}>{sub}</div>}</div>{action&&<div className="actions">{action}</div>}</div>
}
export function Btn({ children, primary = false, violet = false, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean, violet?: boolean }) {
  return (
    <button 
      className={"btn " + (primary ? "primary " : "") + (violet ? "violet" : "")} 
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
