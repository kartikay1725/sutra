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
import { ciService, type CIJob, type CILog, type PRChecksResponse } from '../lib/ci';
import { governanceService, type GovernanceEvaluation } from '../lib/governance';
import { environmentService, type Environment, type Deployment } from '../lib/environments';
import { ConnectSutraButton, ConnectSutraModal, type SutraConnectionState, CANONICAL_MCP_ENDPOINT } from './sutra-connect';

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
  const [changes, setChanges] = useState<Change[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState('all');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await changeService.getAllChanges();
      rows.sort((a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime());
      setChanges(rows);
    } catch (e: any) {
      setError(e?.message || 'Failed to load changes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const filtered = status === 'all' ? changes : changes.filter((c) => c.status === status);

  return (
    <>
      <PageHead
        eyebrow="Engineering"
        title="Changes"
        sub="Real code changes across your repositories produced under SUTRA governance."
        action={
          <RealButton onClick={() => void load()}>
            <I.Activity size={14} /> Refresh
          </RealButton>
        }
      />
      <div className="grid g4" style={{ marginBottom: 18 }}>
        <Stat label="Total Changes" value={String(changes.length)} />
        <Stat label="Proposed" value={String(changes.filter((c) => c.status === 'proposed').length)} />
        <Stat label="Recorded" value={String(changes.filter((c) => c.status === 'recorded').length)} />
        <Stat label="Merged" value={String(changes.filter((c) => c.status === 'merged').length)} />
      </div>
      <Card>
        <div className="card-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="actions">
            {['all', 'proposed', 'recorded', 'merged', 'blocked', 'rejected'].map((value) => (
              <button
                type="button"
                key={value}
                className={`badge ${status === value ? 'aqua' : ''}`}
                style={{ cursor: 'pointer', textTransform: 'capitalize' }}
                onClick={() => setStatus(value)}
              >
                {value === 'all' ? 'All' : value.replaceAll('_', ' ')}
              </button>
            ))}
          </div>
          <span className="meta">{filtered.length} of {changes.length} changes</span>
        </div>
        {error ? (
          <div className="card-pad">
            <div className="sub" style={{ color: '#ff8fa0' }}>
              {error}
            </div>
          </div>
        ) : loading ? (
          <div className="card-pad" style={{ textAlign: 'center', padding: '36px 20px' }}>
            <div className="sub">Loading changes…</div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="card-pad" style={{ textAlign: 'center', padding: '36px 20px' }}>
            <I.GitBranch size={28} className="muted" style={{ marginBottom: 8 }} />
            <div className="title-sm">No changes found</div>
            <div className="sub">No changes match the selected filter.</div>
          </div>
        ) : (
          <div className="list">
            {filtered.map((c) => (
              <Link href={`/changes/${c.id}`} className="list-row" key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 18px', textDecoration: 'none', color: 'inherit' }}>
                <div
                  className="avatar"
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: c.actor_type === 'agent' ? 'rgba(6, 182, 212, 0.15)' : 'rgba(168, 85, 247, 0.15)',
                    color: c.actor_type === 'agent' ? 'var(--cyan)' : 'var(--purple)',
                    flexShrink: 0,
                  }}
                >
                  {c.actor_type === 'agent' ? <I.Bot size={18} /> : <I.UserRound size={18} />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <div className="title-sm" style={{ fontWeight: 600 }}>
                      {c.title || c.intent || `Change #${c.id.slice(0, 8)}`}
                    </div>
                    {c.repository_name && (
                      <span className="badge" style={{ fontSize: 11, background: 'rgba(255, 255, 255, 0.05)' }}>
                        {c.repository_name}
                      </span>
                    )}
                    {c.task_id && (
                      <span className="badge" style={{ fontSize: 11, color: 'var(--cyan)', background: 'rgba(6, 182, 212, 0.1)' }}>
                        Task #{c.task_id.slice(0, 8)}
                      </span>
                    )}
                  </div>
                  <div className="meta" style={{ marginTop: 4, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                    <span>{c.agent_name || c.actor_name || c.actor_id}</span>
                    {c.branch && (
                      <span>
                        <code style={{ fontSize: 11 }}>{c.branch}</code>
                        {c.base_branch && <span> → <code style={{ fontSize: 11 }}>{c.base_branch}</code></span>}
                      </span>
                    )}
                    {c.commits && c.commits.length > 0 && (
                      <span>{c.commits.length} commit{c.commits.length > 1 ? 's' : ''}</span>
                    )}
                    {((c.additions ?? 0) > 0 || (c.deletions ?? 0) > 0) && (
                      <span>
                        <span style={{ color: 'var(--green)' }}>+{c.additions ?? 0}</span>{' '}
                        <span style={{ color: 'var(--red)' }}>−{c.deletions ?? 0}</span>
                      </span>
                    )}
                    <span>{fmtDate(c.updated_at || c.created_at)}</span>
                  </div>
                </div>
                <Badge tone={tone(c.status)} style={{ textTransform: 'capitalize' }}>
                  {c.status.replaceAll('_', ' ')}
                </Badge>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

export function RealChangeDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const [change, setChange] = useState<Change | null>(null);
  const [files, setFiles] = useState<ChangeFile[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [prBusy, setPrBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'commits' | 'files' | 'activity'>('commits');
  const [prChecks, setPrChecks] = useState<PRChecksResponse | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const c = await changeService.getChangeById(id);
      const [f, e, checks] = await Promise.all([
        changeService.getChangeFiles('', '', id).catch(() => []),
        apiAuth<any[]>(`/v1/changes/${id}/events`).catch(() => []),
        c.pull_request_id ? ciService.getPRChecks(c.pull_request_id).catch(() => null) : Promise.resolve(null),
      ]);
      setChange(c);
      setFiles(f);
      setEvents(e);
      setPrChecks(checks);
    } catch (err: any) {
      setError(err?.message || 'Failed to load change');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (id) void load();
  }, [id]);

  const finalize = async () => {
    setBusy(true);
    try {
      const next = await apiAuth<Change>(`/v1/changes/${id}/finalize`, { method: 'POST' });
      setChange(next);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Unable to finalize change');
    } finally {
      setBusy(false);
    }
  };

  const createPR = async () => {
    if (!change) return;
    setPrBusy(true);
    try {
      const pr = await pullRequestService.createPR({
        repository_id: change.repository_id,
        source_change_id: change.id,
        title: change.title || change.intent || `Change #${change.id.slice(0, 8)}`,
        description: change.description || change.intent || null,
        target_branch: change.base_branch || 'main',
        is_draft: false,
      });
      router.push(`/pull-requests/${pr.id}`);
    } catch (e: any) {
      setError(e?.message || 'Unable to create pull request');
    } finally {
      setPrBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="card-pad" style={{ textAlign: 'center', padding: '40px 20px' }}>
        <div className="sub">Loading change…</div>
      </div>
    );
  }

  if (!change) {
    return (
      <div className="card-pad" style={{ textAlign: 'center', padding: '40px 20px' }}>
        <I.AlertCircle size={32} style={{ color: 'var(--red)', marginBottom: 12 }} />
        <div className="h2">Change not found</div>
        <div className="sub" style={{ marginTop: 6 }}>{error || 'The requested change does not exist or you do not have permission to view it.'}</div>
        <div style={{ marginTop: 20 }}>
          <RealButton onClick={() => router.push('/changes')}>Back to Changes</RealButton>
        </div>
      </div>
    );
  }

  const commits = change.commits || [];
  const hasCommits = commits.length > 0;
  const isRecorded = change.status === 'recorded';
  const hasPR = Boolean(change.pull_request_id);

  return (
    <>
      <PageHead
        eyebrow={`Change #${change.id.slice(0, 8)} · ${change.repository_name || 'Repository'}`}
        title={change.title || change.intent || 'Change Record'}
        sub={`${change.actor_type === 'agent' ? 'Agent: ' : 'Author: '}${change.agent_name || change.actor_name || change.actor_id} · Updated ${fmtDate(change.updated_at || change.created_at)}`}
        action={
          <div style={{ display: 'flex', gap: 10 }}>
            {hasPR ? (
              <>
                <Link href={`/pull-requests/${change.pull_request_id}`} className="btn primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <I.GitPullRequest size={14} /> View Pull Request
                </Link>
                {change.github_pr_url && (
                  <a href={change.github_pr_url} target="_blank" rel="noopener noreferrer" className="btn outline" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <I.ExternalLink size={14} /> Open on GitHub
                  </a>
                )}
              </>
            ) : isRecorded || hasCommits ? (
              <RealButton primary onClick={() => void createPR()} disabled={prBusy}>
                <I.GitPullRequest size={14} /> {prBusy ? 'Creating PR…' : 'Create Pull Request'}
              </RealButton>
            ) : change.status !== 'merged' && change.status !== 'rejected' ? (
              <RealButton primary onClick={() => void finalize()} disabled={busy}>
                {busy ? 'Finalizing…' : 'Finalize change'}
              </RealButton>
            ) : null}
          </div>
        }
      />

      {/* SUTRA Pipeline Stepper */}
      <Card style={{ marginBottom: 18 }}>
        <div className="card-pad" style={{ overflowX: 'auto', padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 640 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: change.task_id ? 'var(--green)' : 'var(--muted)' }}>
              {change.task_id ? <I.CheckCircle2 size={16} /> : <I.CircleDot size={16} />}
              <span style={{ fontWeight: 600, fontSize: 13 }}>1. Task</span>
            </div>
            <I.ChevronRight size={14} className="muted" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: change.agent_session_id ? 'var(--green)' : change.actor_type === 'agent' ? 'var(--cyan)' : 'var(--fg)' }}>
              {change.agent_session_id ? <I.CheckCircle2 size={16} /> : <I.CircleDot size={16} />}
              <span style={{ fontWeight: 600, fontSize: 13 }}>2. {change.actor_type === 'agent' ? 'Agent Session' : 'Human Author'}</span>
            </div>
            <I.ChevronRight size={14} className="muted" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--green)' }}>
              <I.CheckCircle2 size={16} />
              <span style={{ fontWeight: 600, fontSize: 13 }}>3. SUTRA Change</span>
            </div>
            <I.ChevronRight size={14} className="muted" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: hasCommits || change.resulting_commit ? 'var(--green)' : 'var(--muted)' }}>
              {hasCommits || change.resulting_commit ? <I.CheckCircle2 size={16} /> : <I.CircleDot size={16} />}
              <span style={{ fontWeight: 600, fontSize: 13 }}>4. Commit(s)</span>
            </div>
            <I.ChevronRight size={14} className="muted" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: hasPR ? 'var(--green)' : 'var(--muted)' }}>
              {hasPR ? <I.CheckCircle2 size={16} /> : <I.CircleDot size={16} />}
              <span style={{ fontWeight: 600, fontSize: 13 }}>5. Pull Request</span>
            </div>
            <I.ChevronRight size={14} className="muted" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: change.status === 'merged' ? 'var(--green)' : 'var(--muted)' }}>
              {change.status === 'merged' ? <I.CheckCircle2 size={16} /> : <I.CircleDot size={16} />}
              <span style={{ fontWeight: 600, fontSize: 13 }}>6. Merged</span>
            </div>
          </div>
        </div>
      </Card>

      {error && (
        <Card style={{ marginBottom: 18 }}>
          <div className="card-pad">
            <div className="sub" style={{ color: '#ff8fa0' }}>{error}</div>
          </div>
        </Card>
      )}

      {/* Main Grid: Left Details & Right Metadata Sidebar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 340px', gap: 20 }}>
        {/* Left Column */}
        <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 20 }}>
          <Card>
            <div style={{ display: 'flex', borderBottom: '1px solid var(--line)' }}>
              <button
                type="button"
                onClick={() => setActiveTab('commits')}
                style={{
                  padding: '12px 18px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: activeTab === 'commits' ? '2px solid var(--cyan)' : '2px solid transparent',
                  color: activeTab === 'commits' ? 'var(--fg)' : 'var(--muted)',
                  fontWeight: activeTab === 'commits' ? 600 : 400,
                  cursor: 'pointer',
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <I.GitCommit size={14} /> Commits with Provenance
                {commits.length > 0 && (
                  <span className="badge" style={{ fontSize: 11, padding: '1px 6px', background: 'rgba(6, 182, 212, 0.15)', color: 'var(--cyan)' }}>
                    {commits.length}
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('files')}
                style={{
                  padding: '12px 18px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: activeTab === 'files' ? '2px solid var(--cyan)' : '2px solid transparent',
                  color: activeTab === 'files' ? 'var(--fg)' : 'var(--muted)',
                  fontWeight: activeTab === 'files' ? 600 : 400,
                  cursor: 'pointer',
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <I.FileCode2 size={14} /> Files Changed
                {files.length > 0 && (
                  <span className="badge" style={{ fontSize: 11, padding: '1px 6px', background: 'rgba(255, 255, 255, 0.08)' }}>
                    {files.length}
                  </span>
                )}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('activity')}
                style={{
                  padding: '12px 18px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: activeTab === 'activity' ? '2px solid var(--cyan)' : '2px solid transparent',
                  color: activeTab === 'activity' ? 'var(--fg)' : 'var(--muted)',
                  fontWeight: activeTab === 'activity' ? 600 : 400,
                  cursor: 'pointer',
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <I.Activity size={14} /> Activity & Audit
                {events.length > 0 && (
                  <span className="badge" style={{ fontSize: 11, padding: '1px 6px', background: 'rgba(255, 255, 255, 0.08)' }}>
                    {events.length}
                  </span>
                )}
              </button>
            </div>

            {/* TAB CONTENT: Commits */}
            {activeTab === 'commits' && (
              <div className="card-pad">
                {commits.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '36px 16px' }}>
                    <I.GitCommit size={28} className="muted" style={{ marginBottom: 10 }} />
                    <div className="title-sm">No Commits Recorded Yet</div>
                    <div className="sub" style={{ maxWidth: 440, margin: '6px auto 0', lineHeight: 1.6 }}>
                      {change.status === 'proposed'
                        ? 'This change is currently proposed. When the assigned agent or engineer commits under the governed session lease, commits will appear here with cryptographic provenance.'
                        : 'No substrate commits are linked to this change.'}
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {commits.map((commit, idx) => {
                      const prov = commit.provenance;
                      const isAgent = prov?.identity_type === 'agent';
                      const isHuman = prov?.identity_type === 'human';
                      const isExternal = prov?.identity_type === 'external';

                      return (
                        <div
                          key={commit.sha || idx}
                          style={{
                            border: isAgent ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid var(--line)',
                            background: isAgent ? 'rgba(16, 185, 129, 0.03)' : 'rgba(255, 255, 255, 0.01)',
                            borderRadius: 10,
                            padding: '16px 18px',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <I.GitCommit size={15} color={isAgent ? 'var(--green)' : 'var(--cyan)'} />
                                <code style={{ fontSize: 13, fontWeight: 600 }}>{commit.sha.slice(0, 10)}</code>
                                {commit.sha === change.resulting_commit && (
                                  <span className="badge green" style={{ fontSize: 10, padding: '1px 6px' }}>Head</span>
                                )}
                              </div>
                              <div className="title-sm" style={{ marginTop: 6, fontWeight: 600, fontSize: 14 }}>
                                {commit.message || 'No commit message recorded.'}
                              </div>
                              <div className="meta" style={{ marginTop: 4 }}>
                                Committed by {commit.author_name || commit.author_email || 'Unknown'} · {fmtDate(commit.committed_at)}
                              </div>
                            </div>

                            {/* Provenance Badge */}
                            <div>
                              {isAgent ? (
                                <Badge tone="green" style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', fontSize: 12 }}>
                                  <I.Bot size={13} /> SUTRA Agent Provenance
                                </Badge>
                              ) : isHuman ? (
                                <Badge tone="violet" style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', fontSize: 12 }}>
                                  <I.UserRound size={13} /> Verified Human Commit
                                </Badge>
                              ) : isExternal ? (
                                <Badge tone="amber" style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', fontSize: 12 }}>
                                  <I.GitCommit size={13} /> External GitHub Commit
                                </Badge>
                              ) : (
                                <Badge tone="aqua" style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', fontSize: 12 }}>
                                  Substrate Commit
                                </Badge>
                              )}
                            </div>
                          </div>

                          {/* Provenance Details Box */}
                          {prov && (
                            <div
                              style={{
                                marginTop: 14,
                                padding: '10px 14px',
                                borderRadius: 8,
                                background: isAgent ? 'rgba(16, 185, 129, 0.08)' : 'rgba(255, 255, 255, 0.03)',
                                fontSize: 12,
                                display: 'flex',
                                flexDirection: 'column',
                                gap: 6,
                              }}
                            >
                              {isAgent && (
                                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                                  <span>
                                    <strong>Agent:</strong> {prov.agent?.name || change.agent_name || 'Autonomous Agent'}
                                  </span>
                                  {prov.session?.id && (
                                    <span>
                                      <strong>Session:</strong> #{prov.session.id.slice(0, 8)}
                                    </span>
                                  )}
                                  {prov.task?.id && (
                                    <span>
                                      <strong>Task:</strong>{' '}
                                      <Link href={`/tasks/${prov.task.id}`} style={{ color: 'var(--cyan)', textDecoration: 'underline' }}>
                                        #{prov.task.id.slice(0, 8)} {prov.task.title ? `(${prov.task.title})` : ''}
                                      </Link>
                                    </span>
                                  )}
                                </div>
                              )}
                              {isHuman && (
                                <div>
                                  <strong>Actor:</strong> {prov.actor_name || commit.author_name || 'SUTRA Operator'}
                                </div>
                              )}
                              {isExternal && (
                                <div style={{ color: 'var(--amber)' }}>
                                  Commit was pushed directly to the substrate branch outside SUTRA session governance.
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT: Files */}
            {activeTab === 'files' && (
              <div className="card-pad">
                {files.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '36px 16px' }}>
                    <I.FileCode2 size={28} className="muted" style={{ marginBottom: 10 }} />
                    <div className="title-sm">No File Modifications Recorded</div>
                    <div className="sub" style={{ margin: '6px auto 0' }}>File diff stats are recorded when commits are pushed.</div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {files.map((f, idx) => (
                      <div
                        key={f.filename || f.path || idx}
                        style={{
                          border: '1px solid var(--line)',
                          borderRadius: 8,
                          padding: '12px 16px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: 12,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                          <I.FileCode2 size={16} className="muted" />
                          <span style={{ fontFamily: 'monospace', fontSize: 13, fontWeight: 500 }}>
                            {f.filename || f.path}
                          </span>
                          {f.operation && (
                            <span className="badge" style={{ fontSize: 10, textTransform: 'uppercase' }}>
                              {f.operation}
                            </span>
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: 10, fontFamily: 'monospace', fontSize: 12, flexShrink: 0 }}>
                          <span style={{ color: 'var(--green)' }}>+{f.additions}</span>
                          <span style={{ color: 'var(--red)' }}>−{f.deletions}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT: Activity */}
            {activeTab === 'activity' && (
              <div className="card-pad">
                {events.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '36px 16px' }}>
                    <I.Activity size={28} className="muted" style={{ marginBottom: 10 }} />
                    <div className="title-sm">No Activity Events Recorded</div>
                  </div>
                ) : (
                  <div className="list">
                    {events.map((e, idx) => (
                      <div className="list-row" key={e.id || idx} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px' }}>
                        <I.Activity size={14} className="muted" />
                        <div style={{ flex: 1 }}>
                          <div className="title-sm" style={{ fontSize: 13 }}>{e.event_type}</div>
                          <div className="meta" style={{ fontSize: 11 }}>
                            {e.from_status || 'initial'} → {e.to_status || 'current'} · {fmtDate(e.created_at)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>

        {/* Right Column / Metadata Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Governance & State Card */}
          <Card>
            <div className="card-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="h2">Governance</div>
              <Badge tone={tone(change.status)} style={{ textTransform: 'capitalize' }}>
                {change.status.replaceAll('_', ' ')}
              </Badge>
            </div>
            <div className="card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <div className="eyebrow">Repository</div>
                <div className="title-sm" style={{ marginTop: 2 }}>
                  {change.repository_name ? (
                    <Link href={`/repositories/${change.repository_name}`} style={{ color: 'var(--cyan)' }}>
                      {change.repository_name}
                    </Link>
                  ) : (
                    change.repository_id
                  )}
                </div>
              </div>
              <div>
                <div className="eyebrow">Actor / Principal</div>
                <div className="title-sm" style={{ marginTop: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
                  {change.actor_type === 'agent' ? <I.Bot size={14} color="var(--cyan)" /> : <I.UserRound size={14} />}
                  <span>{change.agent_name || change.actor_name || change.actor_id}</span>
                </div>
              </div>
              {change.branch && (
                <div>
                  <div className="eyebrow">Branch Scope</div>
                  <div style={{ marginTop: 2, fontSize: 12 }}>
                    <code>{change.branch}</code>
                    {change.base_branch && (
                      <span className="muted"> → <code>{change.base_branch}</code></span>
                    )}
                  </div>
                </div>
              )}
              <div className="grid g2" style={{ marginTop: 4 }}>
                <div>
                  <div className="eyebrow">Base Commit</div>
                  <div className="code" style={{ fontSize: 11 }}>{change.base_commit?.slice(0, 10) || '—'}</div>
                </div>
                <div>
                  <div className="eyebrow">Resulting Commit</div>
                  <div className="code" style={{ fontSize: 11 }}>{change.resulting_commit?.slice(0, 10) || '—'}</div>
                </div>
              </div>
            </div>
          </Card>

          {/* Originating Task Card */}
          <Card>
            <div className="card-head">
              <div className="h2">Originating Task</div>
            </div>
            <div className="card-pad">
              {change.task_id ? (
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <I.CheckSquare size={15} color="var(--cyan)" />
                    <span className="title-sm" style={{ fontWeight: 600 }}>
                      Task #{change.task_id.slice(0, 8)}
                    </span>
                  </div>
                  {change.task_title && (
                    <div className="sub" style={{ marginTop: 6, lineHeight: 1.5 }}>
                      {change.task_title}
                    </div>
                  )}
                  {change.agent_session_id && (
                    <div className="meta" style={{ marginTop: 8 }}>
                      Governed Session: <code style={{ fontSize: 11 }}>#{change.agent_session_id.slice(0, 8)}</code>
                    </div>
                  )}
                  <div style={{ marginTop: 14 }}>
                    <Link href={`/tasks/${change.task_id}`} className="btn" style={{ width: '100%', justifyContent: 'center', display: 'flex', gap: 6 }}>
                      <I.CheckSquare size={14} /> Open Task
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="sub">No originating task is associated with this change.</div>
              )}
            </div>
          </Card>

          {/* Pull Request Card */}
          <Card>
            <div className="card-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="h2">Pull Request</div>
              {hasPR && (
                <Badge tone={tone(change.pull_request_status || 'open')}>
                  {change.pull_request_status || 'open'}
                </Badge>
              )}
            </div>
            <div className="card-pad">
              {hasPR ? (
                <div>
                  <div className="title-sm" style={{ fontWeight: 600 }}>
                    {change.pull_request_title || (change.github_pr_number ? `GitHub PR #${change.github_pr_number}` : `PR #${change.pull_request_id?.slice(0, 8)}`)}
                  </div>
                  <div className="meta" style={{ marginTop: 4 }}>
                    Substrate GitHub Pull Request {change.github_pr_number ? `#${change.github_pr_number}` : ''}
                  </div>

                  {prChecks && (
                    <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 8, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                        {prChecks.overall_status === 'passed' ? <I.CheckCircle2 size={14} style={{ color: 'var(--green)' }} /> : prChecks.overall_status === 'failed' ? <I.XCircle size={14} style={{ color: '#ff4d4f' }} /> : <I.Loader size={14} style={{ color: 'var(--cyan)' }} />}
                        <span>Checks: {prChecks.summary.passed}/{prChecks.summary.total} passed</span>
                      </div>
                      <Badge tone={prChecks.overall_status === 'passed' ? 'green' : prChecks.overall_status === 'failed' ? 'red' : 'aqua'}>
                        {prChecks.governance_verdict === 'READY FOR GOVERNANCE' ? 'Passing' : prChecks.governance_verdict === 'BLOCKED BY CI' ? 'Failing' : 'Running'}
                      </Badge>
                    </div>
                  )}

                  <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <Link href={`/pull-requests/${change.pull_request_id}`} className="btn primary" style={{ width: '100%', justifyContent: 'center', display: 'flex', gap: 6 }}>
                      <I.GitPullRequest size={14} /> View Pull Request
                    </Link>
                    {change.github_pr_url && (
                      <a href={change.github_pr_url} target="_blank" rel="noopener noreferrer" className="btn outline" style={{ width: '100%', justifyContent: 'center', display: 'flex', gap: 6 }}>
                        <I.ExternalLink size={14} /> Open on GitHub
                      </a>
                    )}
                  </div>
                </div>
              ) : isRecorded || hasCommits ? (
                <div>
                  <div className="title-sm">Ready for Pull Request</div>
                  <div className="sub" style={{ marginTop: 4, lineHeight: 1.5 }}>
                    Commits have been recorded and verified under governance. Open a PR to trigger review and merge workflows.
                  </div>
                  <div style={{ marginTop: 14 }}>
                    <RealButton primary onClick={() => void createPR()} disabled={prBusy}>
                      <I.GitPullRequest size={14} /> {prBusy ? 'Creating PR…' : 'Create Pull Request'}
                    </RealButton>
                  </div>
                </div>
              ) : (
                <div className="sub">
                  No pull request opened yet. A pull request can be created once commits are recorded.
                </div>
              )}
            </div>
          </Card>

          {/* Automated Checks Card */}
          {change.checks && change.checks.length > 0 && (
            <Card>
              <div className="card-head">
                <div className="h2">Automated Checks</div>
              </div>
              <div className="card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {change.checks.map((chk, idx) => (
                  <div key={chk.name || idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {chk.status === 'passed' ? <I.CheckCircle2 size={15} color="var(--green)" /> : <I.Loader size={15} color="var(--cyan)" />}
                      <span style={{ fontSize: 13 }}>{chk.name}</span>
                    </div>
                    <Badge tone={chk.status === 'passed' ? 'green' : 'aqua'}>{chk.status}</Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </>
  );
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
        repositoryService.listRepositories().catch(() => []),
      ]);
      setPrs(rows); setRepos(repoRows);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const filtered = filter === 'all' ? prs : prs.filter((p) => p.status === filter);
  const repoName = (id: string) => repos.find((r) => r.id === id)?.name || id.slice(0, 8);

  return <>
    <PageHead
      eyebrow="Delivery"
      title="Pull Requests"
      sub="Autonomous Agent & Human pull requests governed by SUTRA."
      action={<RealButton onClick={() => void load()}><I.Activity size={14}/> Refresh</RealButton>}
    />
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="card-head">
        <div className="actions">
          {['all','open','approved','merged','closed'].map((v) => (
            <button type="button" className={`badge ${filter === v ? 'aqua' : ''}`} key={v} onClick={() => setFilter(v)}>
              {v === 'all' ? 'All' : v}
            </button>
          ))}
        </div>
      </div>
    </div>
    <Card>
      {loading ? (
        <div className="card-pad"><div className="sub">Loading pull requests…</div></div>
      ) : filtered.length === 0 ? (
        <div className="card-pad"><div className="sub">No pull requests found.</div></div>
      ) : (
        <div className="list">
          {filtered.map((pr) => {
            const isAgent = pr.actor_type === 'agent' || Boolean(pr.agent_id) || Boolean(pr.agent_name);
            const rName = pr.repository_name || repoName(pr.repository_id);
            const headRef = pr.head_branch || 'feature';
            const baseRef = pr.target_branch || pr.base_branch || 'main';
            return (
              <div key={pr.id} className="list-row" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px' }}>
                <I.GitPullRequest size={18} style={{ color: pr.status === 'merged' ? 'var(--purple)' : pr.status === 'open' ? 'var(--cyan)' : 'var(--muted)', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    <Link href={`/pull-requests/${pr.id}`} style={{ fontWeight: 600, fontSize: 14, color: 'var(--fg)', textDecoration: 'none' }}>
                      {pr.title}
                    </Link>
                    {pr.github_pr_number && (
                      <span className="badge" style={{ fontSize: 11, background: 'var(--bg-subtle)' }}>
                        GitHub #{pr.github_pr_number}
                      </span>
                    )}
                  </div>
                  <div className="meta" style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 12 }}>
                    <span>{rName}</span>
                    <span>·</span>
                    <span style={{ fontFamily: 'monospace' }}>{headRef} → {baseRef}</span>
                    <span>·</span>
                    <Link href={`/changes/${pr.source_change_id}`} style={{ color: 'var(--muted)', textDecoration: 'none' }}>
                      Change #{pr.source_change_id.slice(0, 8)}
                    </Link>
                    {pr.task_id && (
                      <>
                        <span>·</span>
                        <Link href={`/tasks/${pr.task_id}`} style={{ color: 'var(--muted)', textDecoration: 'none' }}>
                          Task: {pr.task_title || pr.task_id.slice(0, 8)}
                        </Link>
                      </>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                  {isAgent ? (
                    <Badge tone="aqua" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <I.Bot size={12} /> {pr.agent_name || 'Agent'}
                    </Badge>
                  ) : (
                    <Badge tone="gray" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <I.UserRound size={12} /> {pr.actor_name || pr.author_id.slice(0, 8)}
                    </Badge>
                  )}
                  <Badge tone={tone(pr.status)}>{pr.status}</Badge>
                  {pr.github_html_url && (
                    <a
                      href={pr.github_html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title="Open on GitHub"
                      style={{ color: 'var(--muted)', display: 'inline-flex', alignItems: 'center', padding: '4px 6px', borderRadius: 4, border: '1px solid var(--line)' }}
                    >
                      <I.ExternalLink size={13} />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  </>;
}

export function RealPullRequestDetail() {
  const params = useParams<{ id: string }>();
  const prId = params.id;
  const [pr, setPr] = useState<PullRequest | null>(null);
  const [reviews, setReviews] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [checksData, setChecksData] = useState<PRChecksResponse | null>(null);
  const [govData, setGovData] = useState<GovernanceEvaluation | null>(null);
  const [evaluatingGov, setEvaluatingGov] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [p, r, e, repoList, cData, gData] = await Promise.all([
        pullRequestService.getPR(prId),
        pullRequestService.getPRReviews(prId).catch(() => []),
        pullRequestService.getPREvents(prId).catch(() => []),
        repositoryService.listRepositories().catch(() => []),
        ciService.getPRChecks(prId).catch(() => null),
        governanceService.getPRGovernance(prId).catch(() => null),
      ]);
      setPr(p); setReviews(r); setEvents(e); setRepos(repoList); setChecksData(cData); setGovData(gData);
    } catch (e: any) { setError(e?.message || 'Failed to load pull request'); }
  };
  useEffect(() => { void load(); }, [prId]);

  const handleReevaluateGovernance = async () => {
    setEvaluatingGov(true);
    try {
      const updated = await governanceService.evaluatePRGovernance(prId);
      setGovData(updated);
      await load();
    } catch (err: any) {
      setError(err?.message || 'Governance evaluation failed');
    } finally {
      setEvaluatingGov(false);
    }
  };

  const action = async (fn: () => Promise<any>) => {
    setBusy(true);
    try { await fn(); await load(); }
    catch(e:any) { setError(e?.message || 'Action failed'); }
    finally { setBusy(false); }
  };

  if (!pr) return <div className="card-pad"><div className="sub">{error || 'Loading pull request…'}</div></div>;

  const repo = repos.find(r => r.id === pr.repository_id);
  const repoName = pr.repository_name || repo?.name || pr.repository_id.slice(0, 8);
  const isAgent = pr.actor_type === 'agent' || Boolean(pr.agent_id) || Boolean(pr.agent_name);
  const headRef = pr.head_branch || 'feature';
  const baseRef = pr.target_branch || pr.base_branch || 'main';

  return <>
    <PageHead
      eyebrow={`GitHub PR #${pr.github_pr_number || pr.id.slice(0, 8)} · ${repoName}`}
      title={pr.title}
      sub={`${headRef} → ${baseRef} · Created ${fmtDate(pr.created_at)}`}
      action={
        <div className="actions" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {pr.github_html_url && (
            <a
              href={pr.github_html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn primary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <I.ExternalLink size={14} /> Open on GitHub
            </a>
          )}
          <RealButton onClick={() => void action(() => pullRequestService.requestReview(prId))} disabled={busy || ['merged','closed'].includes(pr.status)}>
            Request review
          </RealButton>
          <RealButton onClick={() => void action(() => pullRequestService.approvePR(prId))} disabled={busy || ['merged','closed'].includes(pr.status)}>
            Approve
          </RealButton>
          <RealButton onClick={() => void action(() => pullRequestService.closePR(prId))} disabled={busy || ['merged','closed'].includes(pr.status)}>
            Close
          </RealButton>
          <RealButton primary onClick={() => void action(() => pullRequestService.mergePR(prId))} disabled={busy || ['merged','closed'].includes(pr.status) || !(pr.status === 'approved' || govData?.verdict === 'READY_FOR_MERGE')}>
            <I.GitMerge size={14}/> Merge
          </RealButton>
        </div>
      }
    />

    {error && (
      <Card style={{ marginBottom: 14 }}>
        <div className="card-pad"><div className="sub" style={{ color: '#ff8fa0' }}>{error}</div></div>
      </Card>
    )}

    {/* Key Stats Bar */}
    <div className="grid g4">
      <Stat label="Status" value={pr.status} />
      <Stat 
        label="CI Checks" 
        value={checksData ? `${checksData.summary.passed}/${checksData.summary.total} Passed` : (pr.checks_summary ? `${pr.checks_summary.passed}/${pr.checks_summary.total} Passed` : 'Pending')} 
      />
      <Stat label="Branch Flow" value={`${headRef} → ${baseRef}`} />
      <Stat label="Governance" value={`${reviews.filter((r: any) => r.status === 'approved').length} approvals`} />
    </div>

    {/* SUTRA Context & Provenance Card */}
    <div className="grid g2" style={{ marginTop: 16 }}>
      {/* SUTRA Provenance Card */}
      <Card>
        <div className="card-head">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <I.ShieldCheck size={16} style={{ color: isAgent ? 'var(--cyan)' : 'var(--muted)' }} />
            <div className="h2">SUTRA Provenance & Context</div>
          </div>
          <Badge tone={isAgent ? 'aqua' : 'gray'}>
            {isAgent ? 'Agent-Originated' : 'Human-Originated'}
          </Badge>
        </div>
        <div className="card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {isAgent ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
                <span className="meta">Agent</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                  <I.Bot size={15} style={{ color: 'var(--cyan)' }} />
                  <span>{pr.agent_name || 'Autonomous Agent'}</span>
                  {pr.agent_id && <span className="meta" style={{ fontFamily: 'monospace' }}>({pr.agent_id.slice(0, 8)})</span>}
                </div>
              </div>

              {pr.agent_session_id && (
                <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
                  <span className="meta">Agent Session</span>
                  <span style={{ fontFamily: 'monospace', fontSize: 13 }}>{pr.agent_session_id.slice(0, 12)}…</span>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
                <span className="meta">Originating Task</span>
                {pr.task_id ? (
                  <Link href={`/tasks/${pr.task_id}`} style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--cyan)', fontWeight: 500, textDecoration: 'none' }}>
                    <I.ListTodo size={14} />
                    <span>{pr.task_title || `Task #${pr.task_id.slice(0, 8)}`}</span>
                  </Link>
                ) : (
                  <span className="sub">Direct agent execution (no task bound)</span>
                )}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
                <span className="meta">Originating Change</span>
                <Link href={`/changes/${pr.source_change_id}`} style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--cyan)', fontWeight: 500, textDecoration: 'none' }}>
                  <I.GitBranch size={14} />
                  <span>Change #{pr.source_change_id.slice(0, 8)}</span>
                </Link>
              </div>
            </>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
                <span className="meta">Author</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                  <I.UserRound size={15} />
                  <span>{pr.actor_name || pr.author_id}</span>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
                <span className="meta">Provenance</span>
                <span className="sub">External / human-originated pull request (no agent session).</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
                <span className="meta">Originating Change</span>
                <Link href={`/changes/${pr.source_change_id}`} style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--cyan)', fontWeight: 500, textDecoration: 'none' }}>
                  <I.GitBranch size={14} />
                  <span>Change #{pr.source_change_id.slice(0, 8)}</span>
                </Link>
              </div>
            </>
          )}
        </div>
      </Card>

      {/* Substrate GitHub Context Card */}
      <Card>
        <div className="card-head">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <I.GitPullRequest size={16} />
            <div className="h2">GitHub Substrate PR</div>
          </div>
          {pr.github_pr_number && (
            <Badge tone="aqua">#{pr.github_pr_number}</Badge>
          )}
        </div>
        <div className="card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
            <span className="meta">Repository</span>
            <span style={{ fontWeight: 600 }}>{repoName}</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
            <span className="meta">Branch Flow</span>
            <span style={{ fontFamily: 'monospace', fontSize: 13 }}>{headRef} → {baseRef}</span>
          </div>

          {pr.source_commit && (
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: 8, alignItems: 'center' }}>
              <span className="meta">Source Commit</span>
              <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{pr.source_commit.slice(0, 10)}</span>
            </div>
          )}

          {pr.github_html_url && (
            <div style={{ marginTop: 6 }}>
              <a
                href={pr.github_html_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn primary"
                style={{ width: '100%', justifyContent: 'center', display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <I.ExternalLink size={14} /> Open on GitHub
              </a>
            </div>
          )}
        </div>
      </Card>
    </div>

    {/* Authoritative Checks & CI Verification Card */}
    <Card style={{ marginTop: 16 }}>
      <div className="card-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <I.ShieldCheck size={16} style={{ color: checksData?.overall_status === 'passed' ? 'var(--green)' : checksData?.overall_status === 'failed' ? '#ff4d4f' : 'var(--cyan)' }} />
          <div className="h2">Checks & Automated Verification</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {checksData?.head_sha && (
            <span className="meta" style={{ fontFamily: 'monospace', fontSize: 12 }}>
              HEAD: {checksData.head_sha.slice(0, 8)}
            </span>
          )}
          <Badge tone={checksData?.governance_verdict === 'READY FOR GOVERNANCE' ? 'green' : checksData?.governance_verdict === 'BLOCKED BY CI' ? 'red' : 'aqua'}>
            {checksData?.governance_verdict || pr.checks_verdict || 'PENDING CI'}
          </Badge>
        </div>
      </div>
      <div className="card-pad">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>Overall:</span>
            <span style={{ 
              textTransform: 'capitalize', 
              fontWeight: 600, 
              color: checksData?.overall_status === 'passed' ? 'var(--green)' : checksData?.overall_status === 'failed' ? '#ff4d4f' : 'var(--cyan)' 
            }}>
              {checksData?.overall_status === 'passed' ? 'Passing' : checksData?.overall_status === 'failed' ? 'Failing' : checksData?.overall_status === 'running' ? 'Running' : 'No Checks Reported'}
            </span>
            <span className="sub" style={{ fontSize: 13 }}>
              ({checksData?.summary.passed || 0} passed, {checksData?.summary.failed || 0} failed, {checksData?.summary.running || 0} running)
            </span>
          </div>
          {pr.github_html_url && (
            <a
              href={pr.github_html_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn outline"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '4px 10px' }}
            >
              <I.ExternalLink size={13} /> View on GitHub
            </a>
          )}
        </div>

        {(!checksData?.checks || checksData.checks.length === 0) ? (
          <div className="sub" style={{ padding: '12px 0' }}>No check runs reported for commit {checksData?.head_sha?.slice(0, 8) || 'HEAD'}.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {checksData.checks.map((chk) => (
              <div
                key={chk.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid var(--line)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {chk.status === 'passed' ? (
                    <I.CheckCircle2 size={16} style={{ color: 'var(--green)' }} />
                  ) : chk.status === 'failed' ? (
                    <I.XCircle size={16} style={{ color: '#ff4d4f' }} />
                  ) : chk.status === 'running' ? (
                    <I.Loader size={16} style={{ color: 'var(--cyan)' }} />
                  ) : (
                    <I.CircleDot size={16} style={{ color: 'var(--muted)' }} />
                  )}
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{chk.name}</div>
                    <div className="meta" style={{ fontSize: 12 }}>
                      Source: {chk.source} {chk.started_at ? `· ${fmtDate(chk.started_at)}` : ''}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Badge tone={chk.status === 'passed' ? 'green' : chk.status === 'failed' ? 'red' : 'aqua'}>
                    {chk.conclusion || chk.status}
                  </Badge>
                  {chk.details_url && (
                    <a
                      href={chk.details_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--cyan)', display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, textDecoration: 'none' }}
                    >
                      <span>Details</span> <I.ExternalLink size={12} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>

    {/* SUTRA Governance & Policy Evaluation Card */}
    <Card style={{ marginTop: 16, border: govData?.verdict === 'READY_FOR_APPROVAL' ? '1px solid rgba(16, 185, 129, 0.3)' : govData?.verdict === 'BLOCKED' || govData?.verdict === 'CI_FAILED' || govData?.verdict === 'POLICY_FAILED' ? '1px solid rgba(255, 77, 79, 0.3)' : '1px solid var(--line)' }}>
      <div className="card-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <I.ShieldCheck size={16} style={{ color: govData?.verdict === 'READY_FOR_APPROVAL' ? 'var(--green)' : govData?.verdict === 'NEEDS_REVIEW' ? 'var(--amber)' : govData?.verdict === 'CI_PENDING' ? 'var(--cyan)' : '#ff4d4f' }} />
          <div className="h2">SUTRA Governance & Policy Evaluation</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {govData && (
            <Badge tone={govData.verdict === 'READY_FOR_APPROVAL' ? 'green' : govData.verdict === 'NEEDS_REVIEW' ? 'amber' : govData.verdict === 'CI_PENDING' ? 'aqua' : 'red'}>
              {govData.verdict.replaceAll('_', ' ')}
            </Badge>
          )}
          <button
            onClick={() => void handleReevaluateGovernance()}
            disabled={evaluatingGov}
            className="btn outline"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '4px 10px' }}
          >
            {evaluatingGov ? <I.Loader size={12} /> : <I.Sparkles size={12} />}
            <span>Re-evaluate</span>
          </button>
        </div>
      </div>
      <div className="card-pad">
        {/* 4 Core Pillars Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 16 }}>
          {/* Checks Gate */}
          <div style={{ padding: '12px 14px', borderRadius: 8, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className="sub" style={{ fontSize: 12, fontWeight: 600 }}>Checks & CI</span>
              {govData?.checks.required_passed ? (
                <I.CheckCircle2 size={14} style={{ color: 'var(--green)' }} />
              ) : govData?.checks.failed ? (
                <I.XCircle size={14} style={{ color: '#ff4d4f' }} />
              ) : (
                <I.Clock3 size={14} style={{ color: 'var(--amber)' }} />
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>
              {govData ? (govData.checks.required_passed ? `${govData.checks.passed}/${govData.checks.total} required passing` : govData.checks.failed ? `${govData.checks.failed} checks failing` : 'Checks in progress') : 'Pending evaluation'}
            </div>
          </div>

          {/* Provenance Gate */}
          <div style={{ padding: '12px 14px', borderRadius: 8, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className="sub" style={{ fontSize: 12, fontWeight: 600 }}>Provenance</span>
              {govData?.provenance.verified ? (
                <I.CheckCircle2 size={14} style={{ color: 'var(--green)' }} />
              ) : (
                <I.XCircle size={14} style={{ color: '#ff4d4f' }} />
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>
              {govData?.provenance.verified ? `Verified ${govData.provenance.actor_type === 'agent' ? 'Agent + Session' : 'Human Author'}` : 'Unverified Identity'}
            </div>
          </div>

          {/* Policy & Risk Gate */}
          <div style={{ padding: '12px 14px', borderRadius: 8, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className="sub" style={{ fontSize: 12, fontWeight: 600 }}>Policy & Conflict</span>
              {govData?.policy.passed ? (
                <I.CheckCircle2 size={14} style={{ color: 'var(--green)' }} />
              ) : (
                <I.XCircle size={14} style={{ color: '#ff4d4f' }} />
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>
              {govData?.policy.passed ? `Passed (${govData.policy.conflict_level} conflict)` : 'Policy violation'}
            </div>
          </div>

          {/* Review Gate */}
          <div style={{ padding: '12px 14px', borderRadius: 8, background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--line)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span className="sub" style={{ fontSize: 12, fontWeight: 600 }}>Review Requirements</span>
              {govData?.review.satisfied ? (
                <I.CheckCircle2 size={14} style={{ color: 'var(--green)' }} />
              ) : (
                <I.Clock3 size={14} style={{ color: 'var(--amber)' }} />
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>
              {govData?.review.satisfied ? `Satisfied (${govData.review.actual_approvals}/${govData.review.required_approvals})` : `${govData?.review.actual_approvals || 0}/${govData?.review.required_approvals || 1} approvals recorded`}
            </div>
          </div>
        </div>

        {/* Failed Conditions Callout (if any) */}
        {govData?.failed && govData.failed.length > 0 && (
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(255, 77, 79, 0.08)', border: '1px solid rgba(255, 77, 79, 0.25)', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: 13, color: '#ff4d4f', marginBottom: 6 }}>
              <I.AlertCircle size={15} /> Blocking Governance Conditions:
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 22 }}>
              {govData.failed.map((f, idx) => (
                <div key={idx} style={{ fontSize: 12, color: '#ff8fa0' }}>
                  • {f}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Warnings / Self-Review Disclosures */}
        {govData?.warnings && govData.warnings.length > 0 && (
          <div style={{ padding: '10px 14px', borderRadius: 8, background: 'rgba(234, 179, 8, 0.08)', border: '1px solid rgba(234, 179, 8, 0.25)', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: 13, color: 'var(--amber)', marginBottom: 6 }}>
              <I.AlertTriangle size={15} /> Governance Disclosures:
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingLeft: 22 }}>
              {govData.warnings.map((w, idx) => (
                <div key={idx} style={{ fontSize: 12, color: 'var(--amber)' }}>
                  • {w}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Passed Conditions Summary */}
        {govData?.passed && govData.passed.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {govData.passed.map((p, idx) => (
              <span key={idx} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, padding: '3px 8px', borderRadius: 6, background: 'rgba(16, 185, 129, 0.08)', color: 'var(--green)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                <I.Check size={12} /> {p}
              </span>
            ))}
          </div>
        )}

        {/* Human Approval & Governed Merge Control Box */}
        {pr.status === 'merged' ? (
          <div style={{
            marginTop: 16,
            padding: '16px 18px',
            borderRadius: 8,
            background: 'rgba(16, 185, 129, 0.06)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 16,
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--fg)' }}>
                  Merge Status:
                </span>
                <Badge tone="green">
                  ✓ MERGED
                </Badge>
                {pr.target_commit && (
                  <span style={{ fontSize: 13, fontWeight: 600, fontFamily: 'monospace', color: 'var(--cyan)' }}>
                    Merge SHA: {pr.target_commit.slice(0, 8)}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12, marginTop: 2, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span className="meta">Merged by:</span>
                  <span style={{ fontWeight: 600, color: 'var(--green)' }}>
                    Human Operator
                  </span>
                  {pr.merged_at && (
                    <span className="meta">· {fmtDate(pr.merged_at)}</span>
                  )}
                </div>
                {pr.source_commit && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span className="meta">Reviewed HEAD:</span>
                    <span style={{ fontFamily: 'monospace', color: 'var(--fg)' }}>
                      {pr.source_commit.slice(0, 8)}
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {pr.github_html_url && (
                <a
                  href={pr.github_html_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn outline"
                  style={{ padding: '8px 16px', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  <I.ExternalLink size={14} /> Open on GitHub
                </a>
              )}
            </div>
          </div>
        ) : (
          <div style={{
            marginTop: 16,
            padding: '16px 18px',
            borderRadius: 8,
            background: (pr.status === 'approved' || govData?.verdict === 'READY_FOR_MERGE')
              ? 'rgba(16, 185, 129, 0.04)'
              : 'rgba(255, 255, 255, 0.02)',
            border: (pr.status === 'approved' || govData?.verdict === 'READY_FOR_MERGE')
              ? '1px solid rgba(16, 185, 129, 0.25)'
              : '1px solid var(--line)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 16,
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--fg)' }}>
                  Human Approval Status:
                </span>
                <Badge tone={(pr.status === 'approved' || govData?.verdict === 'READY_FOR_MERGE') ? 'green' : 'amber'}>
                  {(pr.status === 'approved' || govData?.verdict === 'READY_FOR_MERGE')
                    ? 'APPROVED / READY FOR MERGE'
                    : (govData?.verdict === 'READY_FOR_APPROVAL' ? 'READY FOR APPROVAL' : 'NEEDS REVIEW')}
                </Badge>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--muted)' }}>
                  Approvals: {govData?.review.actual_approvals || (pr.status === 'approved' ? 1 : 0)} / {govData?.review.required_approvals || 1}
                </span>
              </div>

              {/* Author vs Approver Provenance */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12, marginTop: 2, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span className="meta">Created by:</span>
                  <span style={{ fontWeight: 600, color: isAgent ? 'var(--cyan)' : 'var(--fg)' }}>
                    {isAgent ? `Agent ${pr.agent_name || 'Atlas'}` : `Human ${pr.actor_name || pr.author_id.slice(0, 8)}`}
                  </span>
                </div>
                {(pr.status === 'approved' || pr.reviewer) && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span className="meta">Approved by:</span>
                    <span style={{ fontWeight: 600, color: 'var(--green)' }}>
                      Human {pr.reviewer?.name || pr.reviewer?.username || 'Reviewer'}
                    </span>
                    {pr.reviewer?.reviewed_at && (
                      <span className="meta">· {fmtDate(pr.reviewer.reviewed_at)}</span>
                    )}
                  </div>
                )}
              </div>

              {/* If not eligible for approval, show explanation */}
              {!(pr.status === 'approved' || govData?.verdict === 'READY_FOR_MERGE') && (
                checksData?.overall_status !== 'passed' && (
                  <div style={{ fontSize: 12, color: 'var(--amber)', display: 'flex', alignItems: 'center', gap: 5 }}>
                    <I.AlertCircle size={13} />
                    Approval unavailable: required CI checks have not passed or are in progress.
                  </div>
                )
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {!(pr.status === 'approved' || govData?.verdict === 'READY_FOR_MERGE') ? (
                <button
                  className="btn primary"
                  onClick={() => void action(async () => {
                    await pullRequestService.approvePR(prId);
                    const updatedGov = await governanceService.getPRGovernance(prId);
                    setGovData(updatedGov);
                  })}
                  disabled={busy || checksData?.overall_status !== 'passed' || govData?.verdict === 'BLOCKED' || govData?.verdict === 'CI_FAILED'}
                  style={{ padding: '8px 16px', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  <I.CheckCircle2 size={15} /> Approve as Human Reviewer
                </button>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: 'var(--green)', fontSize: 13, fontWeight: 600 }}>
                    <I.CheckCircle2 size={16} /> Fully Governed & Approved
                  </span>
                  <button
                    className="btn primary"
                    onClick={() => void action(() => pullRequestService.mergePR(prId))}
                    disabled={busy}
                    style={{ padding: '8px 16px', fontSize: 13, display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 600 }}
                  >
                    <I.GitMerge size={15} /> Merge Pull Request
                  </button>
                </div>
              )}
            </div>
          </div>
        )}      </div>
    </Card>

    {/* PR Description & Intent */}
    {pr.description && (
      <Card style={{ marginTop: 16 }}>
        <div className="card-head">
          <div className="h2">Pull Request Summary & Intent</div>
        </div>
        <div className="card-pad" style={{ fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap', color: 'var(--fg)' }}>
          {pr.description}
        </div>
      </Card>
    )}

    {/* Governance & Audit Timeline */}
    <Card style={{ marginTop: 16 }}>
      <div className="card-head">
        <div className="h2">SUTRA Governance & Audit Log</div>
        <div className="meta">{events.length + reviews.length} audit entries</div>
      </div>
      <div className="list">
        {events.length === 0 && reviews.length === 0 ? (
          <div className="card-pad"><div className="sub">No governance events recorded yet.</div></div>
        ) : (
          <>
            {events.map((e: any) => (
              <div className="list-row" key={e.id}>
                <I.Activity size={14} style={{ color: 'var(--cyan)' }} />
                <div style={{ flex: 1 }}>
                  <div className="title-sm">{e.event_type}</div>
                  <div className="meta">{e.from_status || '—'} → {e.to_status || '—'} · {fmtDate(e.created_at)}</div>
                </div>
              </div>
            ))}
            {reviews.map((r: any) => (
              <div className="list-row" key={r.id}>
                <I.UserRound size={14} style={{ color: r.status === 'approved' ? 'var(--green)' : 'var(--amber)' }} />
                <div style={{ flex: 1 }}>
                  <div className="title-sm">Review: {r.status}</div>
                  <div className="meta">{r.reviewer_id || 'Reviewer'} · {fmtDate(r.created_at)}</div>
                </div>
                <Badge tone={tone(r.status)}>{r.status}</Badge>
              </div>
            ))}
          </>
        )}
      </div>
    </Card>
  </>;
}

export function RealAgents() {
  const [activeTab, setActiveTab] = useState<'active' | 'pending' | 'mcp'>('active');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [pendingRequests, setPendingRequests] = useState<AgentRegistration[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', description: '', provider: '', model: '' });
  const [mcpClient, setMcpClient] = useState<'cursor' | 'claude_desktop' | 'claude_code' | 'windsurf'>('cursor');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<SutraConnectionState>('not_connected');
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const agentList = await agentService.listAgents();
      setAgents(agentList);
      setPendingRequests(await agentService.listPendingRegistrations());
      if (agentList.some(a => a.is_active)) {
        setConnectionState('connected');
      }
    } catch(e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const handleConnectClick = () => {
    setConnectionState('connecting');
    // Check if running in an environment that exposes direct desktop IDE bridge
    const hasDirectBridge = typeof window !== 'undefined' && Boolean((window as any).vscode || (window as any).cursorBridge || (window as any).__SUTRA_MCP_BRIDGE__);
    if (hasDirectBridge) {
      setTimeout(() => {
        setConnectionState('connected');
      }, 500);
    } else {
      // In standard browser environment, direct background process injection is unsupported.
      // Fallback modal is displayed containing the two cards (Custom MCP Settings & API Integration).
      setTimeout(() => {
        setConnectionState('unsupported');
        setIsConnectModalOpen(true);
      }, 350);
    }
  };

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2500);
  };

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

  const mcpEndpoint = CANONICAL_MCP_ENDPOINT;

  // Modern Zero-Token OAuth Configuration Snippets
  const cursorOAuthSnippet = JSON.stringify({
    mcpServers: {
      sutra: {
        url: mcpEndpoint
      }
    }
  }, null, 2);

  const claudeCodeOAuthSnippet = `claude mcp add --transport http sutra ${mcpEndpoint}`;

  const claudeDesktopSnippet = JSON.stringify({
    mcpServers: {
      sutra: {
        url: mcpEndpoint
      }
    }
  }, null, 2);

  const windsurfSnippet = JSON.stringify({
    mcpServers: {
      sutra: {
        serverUrl: mcpEndpoint
      }
    }
  }, null, 2);

  const mcpToolsList = [
    { name: 'sutra_get_context', category: 'Context & Policy', desc: 'Fetches repository rules, active branch policies, open tasks, and engineering standards.' },
    { name: 'sutra_search_knowledge', category: 'Context & Policy', desc: 'Searches the verified institutional Knowledge Graph and codebase intelligence.' },
    { name: 'sutra_start_task', category: 'Task Governance', desc: 'Registers task execution under SUTRA control-plane governance, binding the agent session.' },
    { name: 'sutra_submit_change', category: 'Reconciliation', desc: 'Reconciles terminal-pushed Git commits with SUTRA change control and provenance tracking.' },
    { name: 'sutra_get_status', category: 'Validation & CI', desc: 'Inspects CI pipeline checks, governance evaluations, and merge blockers for a change.' },
    { name: 'sutra_request_merge', category: 'Promotion', desc: 'Requests automated or human-in-the-loop merge authorization for an evaluated change.' },
    { name: 'sutra_get_provenance', category: 'Auditability', desc: 'Retrieves complete immutable cryptographic provenance for files and commits.' },
    { name: 'sutra_create_issue', category: 'Collaboration', desc: 'Files structured tracking issues or blockers directly into SUTRA project governance.' },
  ];

  return <>
    <PageHead
      eyebrow="Autonomy"
      title="Agents & Control Plane"
      sub="Registered autonomous agents, pending authorizations, and Model Context Protocol (MCP) integrations."
      action={
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <ConnectSutraButton
            onClick={handleConnectClick}
            state={connectionState}
          />
          {activeTab === 'active' && (
            <RealButton onClick={() => setShowCreate(!showCreate)}>
              <I.Plus size={14} /> Register New Agent
            </RealButton>
          )}
        </div>
      }
    />

    {/* Tab Navigation */}
    <div style={{ display: 'flex', gap: 20, marginBottom: 20, borderBottom: '1px solid var(--line)', paddingBottom: 2 }}>
      <button
        style={{
          background: 'none', border: 'none', color: activeTab === 'active' ? 'var(--cyan)' : 'var(--muted)',
          fontWeight: activeTab === 'active' ? 600 : 400, cursor: 'pointer', borderBottom: activeTab === 'active' ? '2px solid var(--cyan)' : '2px solid transparent',
          paddingBottom: 10, display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s ease'
        }}
        onClick={() => setActiveTab('active')}
      >
        <I.Bot size={16} /> Active Agents ({agents.length})
      </button>
      <button
        style={{
          background: 'none', border: 'none', color: activeTab === 'pending' ? 'var(--cyan)' : 'var(--muted)',
          fontWeight: activeTab === 'pending' ? 600 : 400, cursor: 'pointer', borderBottom: activeTab === 'pending' ? '2px solid var(--cyan)' : '2px solid transparent',
          paddingBottom: 10, display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s ease'
        }}
        onClick={() => setActiveTab('pending')}
      >
        <I.Clock size={16} /> Pending Requests {pendingRequests.length > 0 && `(${pendingRequests.length})`}
      </button>
      <button
        style={{
          background: 'none', border: 'none', color: activeTab === 'mcp' ? 'var(--cyan)' : 'var(--muted)',
          fontWeight: activeTab === 'mcp' ? 600 : 400, cursor: 'pointer', borderBottom: activeTab === 'mcp' ? '2px solid var(--cyan)' : '2px solid transparent',
          paddingBottom: 10, display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s ease'
        }}
        onClick={() => setActiveTab('mcp')}
      >
        <I.Sparkles size={16} /> Connect SUTRA (MCP)
      </button>
    </div>

    {activeTab === 'active' && (
      <>
        {token && (
          <Card style={{marginBottom:18, borderColor:'rgba(34, 197, 94, 0.4)', background: 'linear-gradient(180deg, rgba(34, 197, 94, 0.08) 0%, rgba(16, 21, 28, 0.6) 100%)'}}>
            <div className="card-pad" style={{ padding: '20px 24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div className="eyebrow" style={{ color: 'var(--green)', fontWeight: 600 }}>Permanent Token Created</div>
                <button
                  className="btn"
                  style={{ padding: '4px 10px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
                  onClick={() => copyToClipboard(token, 'token-banner')}
                >
                  {copiedKey === 'token-banner' ? <I.Check size={14} style={{ color: 'var(--green)' }} /> : <I.Copy size={14} />}
                  {copiedKey === 'token-banner' ? 'Copied' : 'Copy Token'}
                </button>
              </div>
              <div className="code" style={{ wordBreak:'break-all', fontSize: 13, background: 'rgba(0,0,0,0.4)', padding: '10px 14px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.06)' }}>
                {token}
              </div>
              <div className="meta" style={{ marginTop: 8, color: 'var(--text-secondary)' }}>
                Store this token safely. You can immediately use it to connect Cursor, Claude, or Windsurf via the <strong>Connect SUTRA (MCP)</strong> tab.
              </div>
            </div>
          </Card>
        )}

        {showCreate && (
          <Card style={{marginBottom:18, border: '1px solid var(--line-accent)'}}>
            <div className="card-pad form" style={{ padding: '24px' }}>
              <div style={{ marginBottom: 16 }}>
                <h3 style={{ fontSize: 16, fontWeight: 600 }}>Register New Coding Agent</h3>
                <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>Creates a permanent identity in SUTRA with an authoritative access token.</p>
              </div>
              <div className="field">
                <label className="label">Agent Name</label>
                <input className="input" placeholder="e.g. Claude 3.7 Sonnet (Cursor)" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
              </div>
              <div className="field">
                <label className="label">Description</label>
                <input className="input" placeholder="e.g. Lead autonomous coding assistant for feature development" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div className="field">
                  <label className="label">Provider</label>
                  <input className="input" placeholder="e.g. Anthropic, OpenAI, Local" value={form.provider} onChange={e=>setForm({...form,provider:e.target.value})}/>
                </div>
                <div className="field">
                  <label className="label">Model</label>
                  <input className="input" placeholder="e.g. claude-3-7-sonnet" value={form.model} onChange={e=>setForm({...form,model:e.target.value})}/>
                </div>
              </div>
              <div className="actions" style={{ display: 'flex', gap: 10, marginTop: 12 }}>
                <RealButton onClick={()=>setShowCreate(false)}>Cancel</RealButton>
                <RealButton primary onClick={()=>void create()}>Generate Token & Register</RealButton>
              </div>
            </div>
          </Card>
        )}

        <Card>
          {loading ? (
            <div className="card-pad" style={{ textAlign: 'center', padding: '36px 20px' }}>
              <div className="sub">Loading agents…</div>
            </div>
          ) : agents.length === 0 ? (
            <div className="card-pad" style={{ textAlign: 'center', padding: '36px 20px' }}>
              <I.Bot size={32} className="muted" style={{ marginBottom: 10 }} />
              <div className="title-sm" style={{ fontWeight: 600 }}>No agents registered</div>
              <div className="sub" style={{ marginTop: 4 }}>Register an agent above or connect via the MCP tab to enable autonomous coding governance.</div>
            </div>
          ) : (
            <div className="list">
              {agents.map(a => (
                <div className="list-row" key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px' }}>
                  <div className="avatar" style={{
                    width: 36, height: 36, borderRadius: 10, display: 'flex', alignItems: 'center',
                    justifyContent: 'center', background: 'rgba(6, 182, 212, 0.15)', color: 'var(--cyan)'
                  }}>
                    <I.Bot size={18}/>
                  </div>
                  <div style={{flex:1, minWidth: 0}}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="title-sm" style={{ fontWeight: 600 }}>{a.name}</span>
                      <span className="badge" style={{ fontSize: 11, background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)' }}>
                        {a.token_prefix}
                      </span>
                    </div>
                    <div className="meta" style={{ marginTop: 4, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                      <span>{a.provider || 'Provider not set'}</span>
                      <span>·</span>
                      <span>{a.model || 'Model not set'}</span>
                    </div>
                  </div>
                  <Badge tone={tone(a.status)} style={{ textTransform: 'capitalize' }}>{a.status}</Badge>
                  <Link className="btn" href={`/agents/${a.id}`} style={{ padding: '6px 12px', fontSize: 13 }}>Details</Link>
                  <RealButton onClick={()=>void revoke(a.id)}>
                    <I.XCircle size={14}/> Revoke
                  </RealButton>
                </div>
              ))}
            </div>
          )}
        </Card>
      </>
    )}

    {activeTab === 'pending' && (
      <Card>
        {loading ? (
          <div className="card-pad" style={{ textAlign: 'center', padding: '36px 20px' }}><div className="sub">Loading pending requests…</div></div>
        ) : pendingRequests.length === 0 ? (
          <div className="card-pad" style={{ textAlign: 'center', padding: '36px 20px' }}>
            <I.CheckCircle2 size={32} style={{ color: 'var(--green)', marginBottom: 10, opacity: 0.8 }} />
            <div className="title-sm" style={{ fontWeight: 600 }}>All Caught Up</div>
            <div className="sub" style={{ marginTop: 4 }}>No pending agent registration requests awaiting administrative approval.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 16 }}>
            {pendingRequests.map(r => (
              <div key={r.id} style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 18, borderRadius: 12, border: '1px solid var(--line)', background: 'rgba(255,255,255,0.02)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div className="title-sm" style={{ fontSize: 16, fontWeight: 600 }}>{r.agent_name}</div>
                  <Badge tone={tone(r.status)}>{r.status}</Badge>
                </div>
                {r.agent_description && <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{r.agent_description}</div>}
                <div className="meta" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12, opacity: 0.8 }}>
                  <div><strong>Provider:</strong> {r.provider || '—'}</div>
                  <div><strong>Model:</strong> {r.model || '—'}</div>
                  <div><strong>Requested At:</strong> {fmtDate(r.created_at)}</div>
                  <div><strong>Expires At:</strong> {fmtDate(r.expires_at)}</div>
                </div>
                <div style={{ marginTop: 6 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>Requested Capabilities:</div>
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

    {activeTab === 'mcp' && (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Banner */}
        <Card style={{
          border: '1px solid rgba(6, 182, 212, 0.3)',
          background: 'radial-gradient(ellipse at top right, rgba(6, 182, 212, 0.12), transparent 70%), var(--surface)'
        }}>
          <div className="card-pad" style={{ padding: '28px 32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 20 }}>
              <div style={{ maxWidth: 640 }}>
                <div className="eyebrow" style={{ color: 'var(--cyan)', fontWeight: 600, letterSpacing: '0.05em' }}>
                  Model Context Protocol · Streamable HTTP
                </div>
                <h2 style={{ fontSize: 24, fontWeight: 700, marginTop: 6, color: 'var(--text-primary)' }}>
                  Connect Your Coding Agent Once
                </h2>
                <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 8, lineHeight: 1.6 }}>
                  SUTRA provides an enterprise-grade Model Context Protocol (MCP) server over Streamable HTTP.
                  Compatible clients (Cursor, Claude Code, etc.) automatically discover the authorization server,
                  challenge credentials via RFC 9728, and prompt for one-click browser approval.
                </p>
              </div>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <ConnectSutraButton
                  size="large"
                  onClick={handleConnectClick}
                  state={connectionState}
                />
                <a
                  href="/oauth/authorize?client_id=sutra-mcp-client&redirect_uri=https://api.sutra.sudarshanai.com/oauth/callback&response_type=code&scope=sutra:agent&code_challenge=E9Melhoa2OwvFrGMTJguCH5rtx64LxU408W32BgV16g&code_challenge_method=S256"
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => setConnectionState('awaiting_authorization')}
                  className="btn"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '12px 20px', fontWeight: 600, fontSize: 14, borderRadius: 10 }}
                >
                  <I.ExternalLink size={16} /> Test OAuth Flow
                </a>
              </div>
            </div>

            {/* Protocol Spec Badges */}
            <div style={{ display: 'flex', gap: 10, marginTop: 22, flexWrap: 'wrap' }}>
              <span className="badge" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)', fontSize: 12 }}>
                Transport: <strong>Streamable HTTP</strong>
              </span>
              <span className="badge" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)', fontSize: 12 }}>
                Endpoint: <code>/v1/mcp</code>
              </span>
              <span className="badge" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)', fontSize: 12 }}>
                OAuth 2.1 Discovery: <code>/.well-known/oauth-authorization-server</code>
              </span>
              <span className="badge" style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)', fontSize: 12 }}>
                RFC 9728 Resource: <code>/.well-known/oauth-protected-resource</code>
              </span>
            </div>
          </div>
        </Card>

        {/* Diagnostic Status Indicator */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
          padding: '14px 20px',
          borderRadius: 12,
          background: connectionState === 'connected' ? 'rgba(16, 185, 129, 0.08)' : 'rgba(255,255,255,0.03)',
          border: connectionState === 'connected' ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid var(--line)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: connectionState === 'connected' ? '#10b981' : connectionState === 'connecting' ? '#06b6d4' : connectionState === 'awaiting_authorization' ? '#eab308' : '#94a3b8',
              boxShadow: connectionState === 'connected' ? '0 0 8px #10b981' : 'none',
            }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              Connection State:{' '}
              {connectionState === 'not_connected' && 'Not connected'}
              {connectionState === 'connecting' && 'Connecting...'}
              {connectionState === 'awaiting_authorization' && 'Awaiting browser authorization'}
              {connectionState === 'connected' && `Connected (${agents.find(a => a.is_active)?.name || 'Active SUTRA Agent'})`}
              {connectionState === 'unsupported' && 'Unsupported direct injection — Custom configuration active'}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="btn"
              onClick={handleConnectClick}
              style={{ fontSize: 12, padding: '4px 12px' }}
            >
              <I.RefreshCw size={12} /> Check Connection
            </button>
          </div>
        </div>

        {/* Fallback Cards Section */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
          {/* CARD 1: Custom MCP Settings */}
          <Card style={{ border: '1px solid rgba(6, 182, 212, 0.25)', background: 'linear-gradient(180deg, rgba(6, 182, 212, 0.04) 0%, var(--surface) 100%)' }}>
            <div className="card-pad" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Badge tone="aqua">Card 1 · Recommended</Badge>
                  <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Custom MCP Settings</h3>
                </div>
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.5 }}>
                For coding agents that support custom remote MCP servers (Cursor, Claude Code, Windsurf).
                Point your client to the canonical SUTRA MCP endpoint — it handles OAuth discovery and browser approval automatically.
                <strong> No permanent token required.</strong>
              </p>

              {/* Endpoint Display */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Canonical SUTRA MCP Endpoint:
                </div>
                <div style={{ display: 'flex', alignItems: 'center', background: '#07090e', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '8px 12px', gap: 8 }}>
                  <code style={{ flex: 1, fontSize: 13, color: '#38bdf8', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                    {mcpEndpoint}
                  </code>
                  <button
                    type="button"
                    className="btn"
                    style={{ padding: '4px 10px', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={() => copyToClipboard(mcpEndpoint, 'endpoint_tab')}
                  >
                    {copiedKey === 'endpoint_tab' ? <I.Check size={12} style={{ color: 'var(--green)' }} /> : <I.Copy size={12} />}
                    {copiedKey === 'endpoint_tab' ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </div>

              {/* Client Selection */}
              <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                {[
                  { id: 'cursor', label: 'Cursor' },
                  { id: 'claude_code', label: 'Claude Code' },
                  { id: 'windsurf', label: 'Windsurf' },
                  { id: 'claude_desktop', label: 'Claude Desktop' },
                ].map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setMcpClient(c.id as any)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: mcpClient === c.id ? 600 : 400,
                      background: mcpClient === c.id ? 'rgba(6, 182, 212, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                      color: mcpClient === c.id ? '#38bdf8' : 'var(--muted)',
                      border: mcpClient === c.id ? '1px solid rgba(6, 182, 212, 0.35)' : '1px solid transparent',
                      cursor: 'pointer',
                    }}
                  >
                    {c.label}
                  </button>
                ))}
              </div>

              {/* Snippet box */}
              <div style={{ position: 'relative', background: '#07090D', border: '1px solid var(--line)', borderRadius: 8, padding: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <span style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase' }}>
                    {mcpClient === 'cursor' && 'Add to ~/.cursor/mcp.json'}
                    {mcpClient === 'claude_code' && 'Run in Terminal'}
                    {mcpClient === 'windsurf' && 'Add to ~/.codeium/windsurf/mcp_config.json'}
                    {mcpClient === 'claude_desktop' && 'Add to claude_desktop_config.json'}
                  </span>
                  <button
                    type="button"
                    className="btn"
                    style={{ padding: '2px 8px', fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}
                    onClick={() => {
                      const snippet = mcpClient === 'cursor' ? cursorOAuthSnippet : mcpClient === 'claude_code' ? claudeCodeOAuthSnippet : mcpClient === 'windsurf' ? windsurfSnippet : claudeDesktopSnippet;
                      copyToClipboard(snippet, 'tab_snippet');
                    }}
                  >
                    {copiedKey === 'tab_snippet' ? <I.Check size={11} style={{ color: 'var(--green)' }} /> : <I.Copy size={11} />}
                    {copiedKey === 'tab_snippet' ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <pre style={{ margin: 0, fontSize: 12, color: '#38bdf8', fontFamily: 'monospace', overflowX: 'auto' }}>
                  {mcpClient === 'cursor' && cursorOAuthSnippet}
                  {mcpClient === 'claude_code' && claudeCodeOAuthSnippet}
                  {mcpClient === 'windsurf' && windsurfSnippet}
                  {mcpClient === 'claude_desktop' && claudeDesktopSnippet}
                </pre>
              </div>
            </div>
          </Card>

          {/* CARD 2: API Integration */}
          <Card style={{ border: '1px solid rgba(255, 255, 255, 0.1)', background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.02) 0%, var(--surface) 100%)' }}>
            <div className="card-pad" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '100%', boxSizing: 'border-box' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Badge tone="amber">Card 2 · Fallback</Badge>
                <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>API Integration</h3>
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.5 }}>
                Fallback for automated pipelines, CI/CD runners, and background services that cannot use the remote MCP OAuth flow.
                Integrate directly via SUTRA REST APIs with policy and provenance checks.
              </p>

              <div style={{ marginTop: 'auto', background: 'rgba(0,0,0,0.3)', padding: '16px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <I.Book size={18} style={{ color: 'var(--cyan)' }} />
                  <div style={{ fontSize: 13, fontWeight: 600 }}>SUTRA API & Documentation</div>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 14 }}>
                  Comprehensive guides on repository reconciliation, branch governance, and change promotion.
                </div>
                <Link
                  href="/docs"
                  className="btn"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '6px 14px', borderRadius: 6 }}
                >
                  <span>Explore Documentation</span>
                  <I.ExternalLink size={12} />
                </Link>
              </div>

              <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--muted)' }}>
                <I.Lock size={13} style={{ color: 'var(--amber)' }} />
                <span>Zero privileged credentials exposed in the browser.</span>
              </div>
            </div>
          </Card>
        </div>

        {/* 8 Curated Tools Contract Table */}
        <Card>
          <div className="card-pad" style={{ padding: '24px 28px' }}>
            <div style={{ marginBottom: 18 }}>
              <div className="eyebrow" style={{ color: 'var(--cyan)' }}>MCP Contract</div>
              <h3 style={{ fontSize: 17, fontWeight: 600, marginTop: 4 }}>Standard SUTRA Governance Tools (8 Tools)</h3>
              <p style={{ fontSize: 13, color: 'var(--muted)', marginTop: 4 }}>
                These curated tools are automatically exposed to your agent upon connecting to the Streamable HTTP endpoint.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {mcpToolsList.map((tool) => (
                <div
                  key={tool.name}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    borderRadius: 10,
                    background: 'rgba(255,255,255,0.02)',
                    border: '1px solid var(--line)',
                    gap: 16,
                    flexWrap: 'wrap'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 260 }}>
                    <code style={{ fontSize: 13, fontWeight: 600, color: 'var(--cyan)' }}>{tool.name}</code>
                    <span className="badge" style={{ fontSize: 11, background: 'rgba(255,255,255,0.05)' }}>
                      {tool.category}
                    </span>
                  </div>
                  <div style={{ flex: 1, fontSize: 13, color: 'var(--text-secondary)', minWidth: 280 }}>
                    {tool.desc}
                  </div>
                  <Badge tone="aqua">Exposed via MCP</Badge>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    )}

    {/* SUTRA Connect Fallback Dialog Modal */}
    <ConnectSutraModal
      isOpen={isConnectModalOpen}
      onClose={() => setIsConnectModalOpen(false)}
      connectionState={connectionState}
      onStateChange={setConnectionState}
      connectedAgentName={agents.find(a => a.is_active)?.name}
      onConnectAttempt={handleConnectClick}
    />
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
