'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { I } from '../lib/icons';
import { Badge, Card, PageHead, Pipeline, Stat } from './shell';
import { apiAuth } from '../lib/api';
import { authService } from '../lib/auth';
import { repositoryService, type Repository } from '../lib/repositories';
import { changeService, type Change, type ChangeFile } from '../lib/changes';
import { pullRequestService, type PullRequest } from '../lib/pull-requests';
import { agentService, type Agent, type AgentRegistration } from '../lib/agents';
import { ciService, type CIJob, type CILog } from '../lib/ci';
import { environmentService, type Environment, type Deployment } from '../lib/environments';

function tone(status: string) {
  const s = status.toLowerCase();
  if (['merged', 'approved', 'passed', 'success', 'completed', 'active'].includes(s)) return 'green';
  if (['open', 'running', 'proposed', 'review', 'in_progress', 'queued'].includes(s)) return 'aqua';
  if (['failed', 'blocked', 'rejected', 'closed', 'cancelled'].includes(s)) return 'red';
  return 'amber';
}

function fmtDate(value?: string | number | null) {
  if (value == null) return '—';
  const d = typeof value === 'number' ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
}

function RealButton({ children, onClick, disabled = false, primary = false }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean; primary?: boolean }) {
  return (
    <button type="button" className={`btn ${primary ? 'primary' : ''}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

function useOwnedRepositories() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    repositoryService.listRepositories().then((rows) => { if (alive) setRepos(rows); }).catch((e) => { if (alive) setError(e?.message || 'Failed to load repositories'); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);
  return { repos, loading, error };
}

export function RealChanges() {
  const { repos, loading: reposLoading } = useOwnedRepositories();
  const [changes, setChanges] = useState<(Change & { repoName: string })[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState('all');

  const load = async () => {
    setLoading(true);
    try {
      const rows: (Change & { repoName: string })[] = [];
      await Promise.all(repos.map(async (repo) => {
        if (!repo.owner) return;
        const list = await changeService.listChanges(repo.owner, repo.name);
        list.forEach((c) => rows.push({ ...c, repoName: repo.name }));
      }));
      rows.sort((a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime());
      setChanges(rows);
    } catch (e: any) {
      setError(e?.message || 'Failed to load changes');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { if (!reposLoading) void load(); }, [reposLoading, repos]);

  const filtered = status === 'all' ? changes : changes.filter((c) => c.status === status);

  return <>
    <PageHead eyebrow="Engineering" title="Changes" sub="Real code changes across your repositories." action={<RealButton onClick={() => void load()}><I.Activity size={14}/> Refresh</RealButton>} />
    <div className="grid g4" style={{ marginBottom: 15 }}>
      <Stat label="Total" value={String(changes.length)} />
      <Stat label="Proposed" value={String(changes.filter((c) => c.status === 'proposed').length)} />
      <Stat label="Recorded" value={String(changes.filter((c) => c.status === 'recorded').length)} />
      <Stat label="Blocked" value={String(changes.filter((c) => c.status === 'blocked').length)} />
    </div>
    <Card>
      <div className="card-head">
        <div className="actions">
          {['all', 'proposed', 'recorded', 'blocked', 'rejected'].map((value) => (
            <button type="button" key={value} className={`badge ${status === value ? 'aqua' : ''}`} onClick={() => setStatus(value)}>
              {value === 'all' ? 'All' : value.replaceAll('_', ' ')}
            </button>
          ))}
        </div>
      </div>
      {error ? <div className="card-pad"><div className="sub" style={{ color: '#ff8fa0' }}>{error}</div></div> : loading ? <div className="card-pad"><div className="sub">Loading changes…</div></div> : filtered.length === 0 ? <div className="card-pad"><div className="sub">No changes found.</div></div> : <div className="list">
        {filtered.map((c) => <Link href={`/changes/${c.id}`} className="list-row" key={c.id}>
          <div className="avatar" style={{ width: 30, height: 30 }}>{c.actor_type === 'agent' ? <I.Bot size={14}/> : <I.UserRound size={14}/>}</div>
          <div style={{ flex: 1 }}><div className="title-sm">{c.intent || `Change ${c.id.slice(0, 8)}`}</div><div className="meta">{c.repoName} · {c.actor_name || c.actor_id} · {fmtDate(c.updated_at || c.created_at)}</div></div>
          <Badge tone={tone(c.status)}>{c.status.replaceAll('_', ' ')}</Badge>
        </Link>)}
      </div>}
    </Card>
  </>;
}

export function RealChangeDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [change, setChange] = useState<Change | null>(null);
  const [files, setFiles] = useState<ChangeFile[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      const c = await changeService.getChange('', '', id);
      const [f, e] = await Promise.all([
        changeService.getChangeFiles('', '', id).catch(() => []),
        apiAuth<any[]>(`/v1/changes/${id}/events`).catch(() => []),
      ]);
      setChange(c); setFiles(f); setEvents(e);
    } catch (err: any) { setError(err?.message || 'Failed to load change'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, [id]);

  const finalize = async () => {
    setBusy(true);
    try {
      const next = await apiAuth<Change>(`/v1/changes/${id}/finalize`, { method: 'POST' });
      setChange(next);
      await load();
    } catch (e: any) { setError(e?.message || 'Unable to finalize change'); }
    finally { setBusy(false); }
  };

  if (loading) return <div className="card-pad"><div className="sub">Loading change…</div></div>;
  if (!change) return <div className="card-pad"><div className="sub">{error || 'Change not found.'}</div></div>;

  return <>
    <PageHead eyebrow={`Change #${change.id.slice(0, 8)}`} title={change.intent || 'Change'} sub={`${change.actor_name || change.actor_id} · updated ${fmtDate(change.updated_at)}`} action={change.status !== 'merged' && change.status !== 'rejected' ? <RealButton primary onClick={() => void finalize()} disabled={busy}>{busy ? 'Finalizing…' : 'Finalize change'}</RealButton> : undefined}/>
    <Pipeline/>
    {error && <Card><div className="card-pad"><div className="sub" style={{ color: '#ff8fa0' }}>{error}</div></div></Card>}
    <div className="grid g2">
      <Card><div className="card-head"><div><div className="h2">Change metadata</div><div className="sub">Backend-backed change state</div></div><Badge tone={tone(change.status)}>{change.status}</Badge></div><div className="card-pad"><div className="grid g2"><div><div className="eyebrow">Actor</div><div className="title-sm">{change.actor_name || change.actor_id}</div></div><div><div className="eyebrow">Risk</div><div className="title-sm">{change.risk_level}</div></div><div><div className="eyebrow">Base commit</div><div className="code">{change.base_commit?.slice(0, 12) || '—'}</div></div><div><div className="eyebrow">Resulting commit</div><div className="code">{change.resulting_commit?.slice(0, 12) || '—'}</div></div></div></div></Card>
      <Card><div className="card-head"><div className="h2">Files</div><Badge>{files.length}</Badge></div><div className="list">{files.length === 0 ? <div className="card-pad"><div className="sub">No change files recorded.</div></div> : files.map((f) => <div className="list-row" key={f.filename}><I.FileCode2 size={14}/><div style={{ flex: 1 }}><div className="title-sm">{f.filename}</div><div className="meta">{f.operation} · +{f.additions} −{f.deletions}</div></div></div>)}</div></Card>
    </div>
    <Card style={{ marginTop: 14 }}><div className="card-head"><div className="h2">Activity</div><Badge>{events.length}</Badge></div><div className="list">{events.length === 0 ? <div className="card-pad"><div className="sub">No change events recorded.</div></div> : events.map((e) => <div className="list-row" key={e.id}><I.Activity size={14}/><div><div className="title-sm">{e.event_type}</div><div className="meta">{e.from_status || '—'} → {e.to_status || '—'} · {fmtDate(e.created_at)}</div></div></div>)}</div></Card>
  </>;
}

export function RealPullRequests() {
  const [prs, setPrs] = useState<PullRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [repos, setRepos] = useState<Repository[]>([]);
  const load = async () => {
    setLoading(true);
    try {
      const [rows, repoRows] = await Promise.all([
        apiAuth<PullRequest[]>('/v1/pull-requests?limit=100'),
        repositoryService.listRepositories(),
      ]);
      setPrs(rows); setRepos(repoRows);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const filtered = filter === 'all' ? prs : prs.filter((p) => p.status === filter);
  const repoName = (id: string) => repos.find((r) => r.id === id)?.name || id.slice(0, 8);
  return <>
    <PageHead eyebrow="Delivery" title="Pull Requests" sub="Real pull requests from SUTRA." action={<RealButton onClick={() => void load()}><I.Activity size={14}/> Refresh</RealButton>} />
    <div className="card" style={{ marginBottom: 14 }}><div className="card-head"><div className="actions">{['all','open','approved','merged','closed'].map((v) => <button type="button" className={`badge ${filter === v ? 'aqua' : ''}`} key={v} onClick={() => setFilter(v)}>{v === 'all' ? 'All' : v}</button>)}</div></div></div>
    <Card>{loading ? <div className="card-pad"><div className="sub">Loading pull requests…</div></div> : filtered.length === 0 ? <div className="card-pad"><div className="sub">No pull requests found.</div></div> : <div className="list">{filtered.map((pr) => <Link href={`/pull-requests/${pr.id}`} className="list-row" key={pr.id}><I.GitPullRequest size={15}/><div style={{flex:1}}><div className="title-sm">{pr.title}</div><div className="meta">{repoName(pr.repository_id)} · {pr.author_id} · {pr.source_change_id.slice(0,8)}</div></div><Badge tone={tone(pr.status)}>{pr.status}</Badge></Link>)}</div>}</Card>
  </>;
}

export function RealPullRequestDetail() {
  const params = useParams<{ id: string }>();
  const prId = params.id;
  const [pr, setPr] = useState<PullRequest | null>(null);
  const [reviews, setReviews] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [diff, setDiff] = useState<any>(null);
  const [ci, setCi] = useState<CIJob[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    try {
      const [p, r, e, d, jobs] = await Promise.all([
        pullRequestService.getPR(prId),
        pullRequestService.getPRReviews(prId).catch(() => []),
        pullRequestService.getPREvents(prId).catch(() => []),
        apiAuth<any>(`/v1/pull-requests/${prId}/diff`).catch(() => ({ files: [] })),
        ciService.listJobsForPR(prId).catch(() => []),
      ]);
      setPr(p); setReviews(r); setEvents(e); setDiff(d); setCi(jobs);
    } catch (e: any) { setError(e?.message || 'Failed to load pull request'); }
  };
  useEffect(() => { void load(); }, [prId]);
  const action = async (fn: () => Promise<any>) => { setBusy(true); try { await fn(); await load(); } catch(e:any) { setError(e?.message || 'Action failed'); } finally { setBusy(false); } };
  if (!pr) return <div className="card-pad"><div className="sub">{error || 'Loading pull request…'}</div></div>;
  return <>
    <PageHead eyebrow={`Pull Request #${pr.id.slice(0,8)}`} title={pr.title} sub={`${pr.source_change_id.slice(0,8)} · ${pr.target_branch}`} action={<div className="actions"><RealButton onClick={() => void action(() => pullRequestService.requestReview(prId))} disabled={busy || ['merged','closed'].includes(pr.status)}>Request review</RealButton><RealButton onClick={() => void action(() => pullRequestService.approvePR(prId))} disabled={busy || ['merged','closed'].includes(pr.status)}>Approve</RealButton><RealButton onClick={() => void action(() => pullRequestService.closePR(prId))} disabled={busy || ['merged','closed'].includes(pr.status)}>Close</RealButton><RealButton primary onClick={() => void action(() => pullRequestService.mergePR(prId))} disabled={busy || ['merged','closed'].includes(pr.status)}><I.GitMerge size={14}/> Merge</RealButton></div>} />
    <div className="grid g4"><Stat label="Status" value={pr.status}/><Stat label="Target" value={pr.target_branch}/><Stat label="Reviews" value={String(reviews.length)}/><Stat label="CI jobs" value={String(ci.length)}/></div>
    {error && <Card style={{marginTop:14}}><div className="card-pad"><div className="sub" style={{color:'#ff8fa0'}}>{error}</div></div></Card>}
    <div className="grid g2" style={{marginTop:14}}>
      <Card><div className="card-head"><div className="h2">Diff</div><Badge tone="aqua">{Array.isArray(diff?.files) ? diff.files.length : 0} files</Badge></div><div className="list">{Array.isArray(diff?.files) && diff.files.length ? diff.files.map((f:any) => <div className="list-row" key={f.path || f.filename}><I.FileCode2 size={14}/><div><div className="title-sm">{f.path || f.filename}</div><div className="meta">{f.status || f.operation || 'changed'}</div></div></div>) : <div className="card-pad"><div className="sub">No diff files returned.</div></div>}</div></Card>
      <Card><div className="card-head"><div className="h2">CI</div><RealButton onClick={() => void action(() => ciService.triggerRun(prId))} disabled={busy}>Run CI</RealButton></div><div className="list">{ci.length === 0 ? <div className="card-pad"><div className="sub">No CI jobs.</div></div> : ci.map((job) => <Link href={`/ci/${job.id}`} className="list-row" key={job.id}><I.Workflow size={14}/><div style={{flex:1}}><div className="title-sm">{job.status}</div><div className="meta">{job.commit_sha.slice(0,8)} · {fmtDate(job.created_at)}</div></div><Badge tone={tone(job.status)}>{job.status}</Badge></Link>)}</div></Card>
    </div>
    <Card style={{marginTop:14}}><div className="card-head"><div className="h2">Review & activity</div></div><div className="list">{events.map((e:any) => <div className="list-row" key={e.id}><I.Activity size={14}/><div><div className="title-sm">{e.event_type}</div><div className="meta">{e.from_status || '—'} → {e.to_status || '—'} · {fmtDate(e.created_at)}</div></div></div>)}{reviews.map((r:any) => <div className="list-row" key={r.id}><I.UserRound size={14}/><div><div className="title-sm">Review {r.status}</div><div className="meta">{r.reviewer_id || 'Unassigned'} · {fmtDate(r.created_at)}</div></div></div>)}</div></Card>
  </>;
}

export function RealAgents() {
  const [activeTab, setActiveTab] = useState<'active' | 'pending'>('active');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [pendingRequests, setPendingRequests] = useState<AgentRegistration[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', description: '', provider: '', model: '' });

  const load = async () => {
    setLoading(true);
    try {
      setAgents(await agentService.listAgents());
      setPendingRequests(await agentService.listPendingRegistrations());
    } catch(e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const create = async () => {
    if (!form.name.trim()) return;
    try {
      const created = await agentService.createAgent(form);
      setToken(created.token);
      setShowCreate(false);
      setForm({name:'',description:'',provider:'',model:''});
      await load();
    } catch(e:any) {
      alert(e?.message || 'Failed to register agent');
    }
  };

  const revoke = async (id: string) => {
    if (!confirm('Revoke this agent?')) return;
    try {
      await agentService.revokeAgent(id);
      await load();
    } catch(e:any) {
      alert(e?.message || 'Failed to revoke agent');
    }
  };

  const handleApprove = async (id: string) => {
    const requestToApprove = pendingRequests.find(r => r.id === id);
    if (!requestToApprove) return;
    if (!confirm(`Are you sure you want to approve agent: ${requestToApprove.agent_name}?`)) return;
    try {
      await agentService.approveRegistration(id);
      alert('Agent approved.');
      await load();
    } catch(e:any) {
      alert(e?.message || 'Failed to approve registration request');
    }
  };

  const handleReject = async (id: string) => {
    const requestToReject = pendingRequests.find(r => r.id === id);
    if (!requestToReject) return;
    if (!confirm(`Are you sure you want to reject agent: ${requestToReject.agent_name}?`)) return;
    try {
      await agentService.rejectRegistration(id);
      alert('Agent rejected.');
      await load();
    } catch(e:any) {
      alert(e?.message || 'Failed to reject registration request');
    }
  };

  return <>
    <PageHead eyebrow="Autonomy" title="Agents" sub="Registered agents owned by your SUTRA account." />

    {/* Tab Navigation */}
    <div style={{ display: 'flex', gap: 16, marginBottom: 16, borderBottom: '1px solid var(--line)', paddingBottom: 8 }}>
      <button
        style={{
          background: 'none', border: 'none', color: activeTab === 'active' ? 'var(--cyan)' : 'var(--muted)',
          fontWeight: activeTab === 'active' ? 600 : 400, cursor: 'pointer', borderBottom: activeTab === 'active' ? '2px solid var(--cyan)' : 'none',
          paddingBottom: 8
        }}
        onClick={() => setActiveTab('active')}
      >
        Active Agents
      </button>
      <button
        style={{
          background: 'none', border: 'none', color: activeTab === 'pending' ? 'var(--cyan)' : 'var(--muted)',
          fontWeight: activeTab === 'pending' ? 600 : 400, cursor: 'pointer', borderBottom: activeTab === 'pending' ? '2px solid var(--cyan)' : 'none',
          paddingBottom: 8
        }}
        onClick={() => setActiveTab('pending')}
      >
        Pending Requests {pendingRequests.length > 0 && `(${pendingRequests.length})`}
      </button>
    </div>

    {activeTab === 'active' && (
      <>
        {token && <Card style={{marginBottom:14,borderColor:'rgba(105,230,168,.22)'}}><div className="card-pad"><div className="eyebrow">Save this token now</div><div className="code" style={{wordBreak:'break-all'}}>{token}</div><div className="meta">The backend only returns the newly generated token at creation time.</div></div></Card>}
        {showCreate && <Card style={{marginBottom:14}}><div className="card-pad form"><div className="field"><label className="label">Name</label><input className="input" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/></div><div className="field"><label className="label">Description</label><input className="input" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></div><div className="field"><label className="label">Provider</label><input className="input" value={form.provider} onChange={e=>setForm({...form,provider:e.target.value})}/></div><div className="field"><label className="label">Model</label><input className="input" value={form.model} onChange={e=>setForm({...form,model:e.target.value})}/></div><div className="actions"><RealButton onClick={()=>setShowCreate(false)}>Cancel</RealButton><RealButton primary onClick={()=>void create()}>Create agent</RealButton></div></div></Card>}
        <Card>{loading ? <div className="card-pad"><div className="sub">Loading agents…</div></div> : agents.length === 0 ? <div className="card-pad"><div className="sub">No agents registered.</div></div> : <div className="list">{agents.map(a => <div className="list-row" key={a.id}><div className="avatar"><I.Bot size={14}/></div><div style={{flex:1}}><div className="title-sm">{a.name}</div><div className="meta">{a.provider || 'Provider not set'} · {a.model || 'Model not set'} · {a.token_prefix}</div></div><Badge tone={tone(a.status)}>{a.status}</Badge><Link className="btn" href={`/agents/${a.id}`}>Details</Link><RealButton onClick={()=>void revoke(a.id)}><I.XCircle size={14}/> Revoke</RealButton></div>)}</div>}</Card>
      </>
    )}

    {activeTab === 'pending' && (
      <Card>
        {loading ? (
          <div className="card-pad"><div className="sub">Loading pending requests…</div></div>
        ) : pendingRequests.length === 0 ? (
          <div className="card-pad"><div className="sub">No pending agent requests.</div></div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 14 }}>
            {pendingRequests.map(r => (
              <div key={r.id} style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 16, borderRadius: 8, border: '1px solid var(--line)', background: 'rgba(255,255,255,0.02)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div className="title-sm" style={{ fontSize: 16, fontWeight: 600 }}>{r.agent_name}</div>
                  <Badge tone={tone(r.status)}>{r.status}</Badge>
                </div>
                {r.agent_description && <div style={{ fontSize: 13, opacity: 0.8 }}>{r.agent_description}</div>}
                <div className="meta" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12, opacity: 0.6 }}>
                  <div><strong>Provider:</strong> {r.provider || '—'}</div>
                  <div><strong>Model:</strong> {r.model || '—'}</div>
                  <div><strong>Requested At:</strong> {fmtDate(r.created_at)}</div>
                  <div><strong>Expires At:</strong> {fmtDate(r.expires_at)}</div>
                </div>
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Requested Capabilities:</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {r.requested_capabilities && r.requested_capabilities.length > 0 ? (
                      r.requested_capabilities.map((cap: string) => (
                        <Badge key={cap} tone="aqua">{cap}</Badge>
                      ))
                    ) : (
                      <span style={{ fontSize: 12, opacity: 0.5 }}>None</span>
                    )}
                  </div>
                </div>
                <div className="actions" style={{ display: 'flex', gap: 10, marginTop: 12 }}>
                  <RealButton primary onClick={() => void handleApprove(r.id)}>Approve Agent</RealButton>
                  <RealButton onClick={() => void handleReject(r.id)}>Reject Agent</RealButton>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    )}
  </>;
}

export function RealAgentDetail() {
  const params = useParams<{id:string}>();
  const [agent,setAgent]=useState<Agent|null>(null);
  const [loading,setLoading]=useState(true);
  useEffect(()=>{ agentService.listAgents().then(rows=>setAgent(rows.find(a=>a.id===params.id)||null)).catch(console.error).finally(()=>setLoading(false)); },[params.id]);
  if (loading) return <div className="card-pad"><div className="sub">Loading agent…</div></div>;
  if (!agent) return <div className="card-pad"><div className="sub">Agent not found.</div></div>;
  return <><PageHead eyebrow="Agent" title={agent.name} sub={agent.description || 'No description.'} action={<Link className="btn" href="/agents">Back</Link>} /><div className="grid g4"><Stat label="Status" value={agent.status}/><Stat label="Provider" value={agent.provider || '—'}/><Stat label="Model" value={agent.model || '—'}/><Stat label="Token" value={agent.token_prefix}/></div><Card style={{marginTop:14}}><div className="card-head"><div className="h2">Capabilities & runtime</div></div><div className="card-pad"><div className="sub">This backend exposes registration and session APIs. Run history is not currently exposed through a user-facing agent-run history endpoint, so no fake run history is shown here.</div></div></Card></>;
}

export function RealCI() {
  const [prs,setPrs]=useState<PullRequest[]>([]);
  const [jobs,setJobs]=useState<(CIJob & {prTitle:string})[]>([]);
  const [loading,setLoading]=useState(true);
  const load=async()=>{setLoading(true);try{const rows=await apiAuth<PullRequest[]>('/v1/pull-requests?limit=100');setPrs(rows);const results=await Promise.all(rows.map(async pr=>(await ciService.listJobsForPR(pr.id).catch(()=>[])).map(j=>({...j,prTitle:pr.title}))));setJobs(results.flat().sort((a,b)=>new Date(b.created_at).getTime()-new Date(a.created_at).getTime()));}finally{setLoading(false);}};
  useEffect(()=>{void load();},[]);
  const running=jobs.filter(j=>j.status==='running').length, passed=jobs.filter(j=>j.status==='passed').length, failed=jobs.filter(j=>j.status==='failed').length;
  return <><PageHead eyebrow="Delivery" title="CI / Pipelines" sub="Real CI jobs attached to pull requests." action={<RealButton onClick={()=>void load()}><I.Activity size={14}/> Refresh</RealButton>} /><div className="grid g4"><Stat label="Running" value={String(running)}/><Stat label="Passed" value={String(passed)}/><Stat label="Failed" value={String(failed)}/><Stat label="Total jobs" value={String(jobs.length)}/></div><Card style={{marginTop:14}}>{loading?<div className="card-pad"><div className="sub">Loading CI jobs…</div></div>:jobs.length===0?<div className="card-pad"><div className="sub">No CI jobs found.</div></div>:<div className="list">{jobs.map(j=><Link href={`/ci/${j.id}`} className="list-row" key={j.id}><I.Workflow size={14}/><div style={{flex:1}}><div className="title-sm">{j.prTitle}</div><div className="meta">{j.commit_sha.slice(0,8)} · {fmtDate(j.created_at)}</div></div><Badge tone={tone(j.status)}>{j.status}</Badge></Link>)}</div>}</Card></>;
}

export function RealCIJob() {
  const params=useParams<{id:string}>();
  const [job,setJob]=useState<CIJob|null>(null); const [logs,setLogs]=useState<CILog|null>(null); const [prTitle,setPrTitle]=useState('CI job'); const [busy,setBusy]=useState(false); const [loading,setLoading]=useState(true);
  const load=async()=>{setLoading(true);try{const prs=await apiAuth<PullRequest[]>('/v1/pull-requests?limit=100');for(const pr of prs){const jobs=await ciService.listJobsForPR(pr.id).catch(()=>[]);const found=jobs.find(j=>j.id===params.id);if(found){setJob(found);setPrTitle(pr.title);setLogs(await ciService.getLogs(pr.id,found.id).catch(()=>null));break;}}}finally{setLoading(false);}};
  useEffect(()=>{void load();},[params.id]);
  const cancel=async()=>{if(!job||job.status!=='running')return;setBusy(true);try{await ciService.cancelJob(job.pull_request_id,job.id);await load();}finally{setBusy(false);}};
  if(loading)return <div className="card-pad"><div className="sub">Loading CI job…</div></div>;
  if(!job)return <div className="card-pad"><div className="sub">CI job not found.</div></div>;
  return <><PageHead eyebrow={`CI #${job.id.slice(0,8)}`} title={prTitle} sub={`Commit ${job.commit_sha.slice(0,12)} · ${job.status}`} action={job.status==='running'?<RealButton onClick={()=>void cancel()} disabled={busy}>Cancel</RealButton>:undefined}/><div className="grid g3"><Stat label="Status" value={job.status}/><Stat label="Exit code" value={job.exit_code == null ? '—' : String(job.exit_code)}/><Stat label="Trigger" value={job.trigger}/></div><Card style={{marginTop:14}}><div className="card-head"><div className="h2">Logs</div><Badge tone={tone(job.status)}>{job.status}</Badge></div><div className="terminal"><div style={{whiteSpace:'pre-wrap'}}>{logs?.output_log || 'No logs available.'}</div></div></Card></>;
}

export function RealDeployments() {
  const { repos, loading: reposLoading } = useOwnedRepositories();
  const [rows,setRows]=useState<(Deployment & {environmentName:string; repoName:string})[]>([]);
  const [loading,setLoading]=useState(true);
  const [showCreate,setShowCreate]=useState(false);
  const [environments,setEnvironments]=useState<(Environment & {repoName:string})[]>([]);
  const [envId,setEnvId]=useState('');
  const [commitSha,setCommitSha]=useState('');
  const load=async()=>{setLoading(true);try{const allEnvs:(Environment & {repoName:string})[]=[];for(const repo of repos){if(!repo.owner)continue;const envs=await environmentService.listEnvironments(repo.owner,repo.name).catch(()=>[]);envs.forEach(e=>allEnvs.push({...e,repoName:repo.name}));}setEnvironments(allEnvs);const deployed=await Promise.all(allEnvs.map(async e=>(await environmentService.listDeployments(e.id).catch(()=>[])).map(d=>({...d,environmentName:e.name,repoName:e.repoName}))));setRows(deployed.flat().sort((a,b)=>new Date(b.created_at).getTime()-new Date(a.created_at).getTime()));}finally{setLoading(false);}};
  useEffect(()=>{if(!reposLoading)void load();},[reposLoading,repos]);
  const create=async()=>{if(!envId||!commitSha.trim())return;try{await apiAuth(`/v1/environments/${envId}/deployments`,{method:'POST',body:JSON.stringify({commit_sha:commitSha.trim(),change_id:null})});setShowCreate(false);setEnvId('');setCommitSha('');await load();}catch(e:any){alert(e?.message||'Failed to create deployment');}};
  return <><PageHead eyebrow="Delivery" title="Deployments" sub="Real deployment records from repository environments." action={<RealButton primary onClick={()=>setShowCreate(true)}><I.Plus size={14}/> New deployment</RealButton>} />{showCreate&&<Card style={{marginBottom:14}}><div className="card-pad form"><div className="field"><label className="label">Environment</label><select className="input" value={envId} onChange={e=>setEnvId(e.target.value)}><option value="">Select environment</option>{environments.map(e=><option key={e.id} value={e.id}>{e.repoName} · {e.name}</option>)}</select></div><div className="field"><label className="label">Commit SHA</label><input className="input" value={commitSha} onChange={e=>setCommitSha(e.target.value)} placeholder="40-character Git SHA"/></div><div className="actions"><RealButton onClick={()=>setShowCreate(false)}>Cancel</RealButton><RealButton primary onClick={()=>void create()}>Create deployment</RealButton></div></div></Card>}{loading?<div className="card-pad"><div className="sub">Loading deployments…</div></div>:rows.length===0?<Card><div className="card-pad"><div className="sub">No deployments found.</div></div></Card>:<Card><div className="list">{rows.map(d=><div className="list-row" key={d.id}><I.Rocket size={14}/><div style={{flex:1}}><div className="title-sm">{d.repoName} · {d.environmentName}</div><div className="meta">{d.commit_sha.slice(0,12)} · {fmtDate(d.created_at)}</div></div><Badge tone={tone(d.status)}>{d.status}</Badge><span className="meta">{d.id.slice(0,8)}</span></div>)}</div></Card>}</>;
}
