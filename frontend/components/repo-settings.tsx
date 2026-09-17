'use client';

import React, { useState, useEffect, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Shield,
  ShieldCheck,
  GitBranch,
  GitPullRequest,
  Sliders,
  Check,
  X,
  AlertTriangle,
  Trash2,
  Edit3,
  Plus,
  Search,
  Copy,
  ExternalLink,
  Lock,
  Unlock,
  Bot,
  Sparkles,
  Workflow,
  CheckCircle2,
  Users,
  ListTodo,
  RefreshCw,
  GitMerge,
  Info,
  Layers,
  ArrowRight,
} from "lucide-react";
import { repositoryService, Repository } from "../lib/repositories";
import {
  branchProtectionService,
  BranchProtectionRule,
  BranchProtectionWrite,
} from "../lib/branch_protection";
import { ConfirmModal } from "./ConfirmModal";
import { authService } from "../lib/auth";
import { SkeletonRepoSettings } from "./skeleton";

export interface RepoPolicies {
  require_task_linkage?: boolean;
  enforce_governed_provenance?: boolean;
  require_clean_conflict?: boolean;
  require_ci_passed?: boolean;
  require_agent_review?: boolean;
  require_no_blocking_findings?: boolean;
  disallow_self_approval?: boolean;
  min_approvals?: number;
}

interface RepositoryBranch {
  name: string;
  commit: string;
  protected?: boolean;
}

type SettingsTab = "general" | "policies" | "branches" | "danger";
type DangerAction = "delete" | "visibility" | "transfer" | "";

const DEFAULT_POLICIES: RepoPolicies = {
  require_task_linkage: true,
  enforce_governed_provenance: true,
  require_clean_conflict: true,
  require_ci_passed: false,
  require_agent_review: false,
  require_no_blocking_findings: false,
  disallow_self_approval: true,
  min_approvals: 1,
};

const EMPTY_RULE = (repoId: string, defaultBranch = "main"): BranchProtectionRule => ({
  id: "",
  repository_id: repoId,
  branch_pattern: defaultBranch,
  enabled: true,
  required_approvals: 1,
  require_change_review: true,
  require_clean_conflict: true,
  require_resolved_threads: true,
  require_agent_review: false,
  require_no_blocking_agent_findings: false,
  allow_author_self_approval: false,
  require_ci_passed: false,
  created_by: "",
  updated_by: "",
  created_at: "",
  updated_at: "",
});

export function RepoSettings() {
  const params = useParams<{ name: string }>();
  const router = useRouter();
  const repoParam = decodeURIComponent(params?.name || "");

  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [repo, setRepo] = useState<Repository | null>(null);
  const [repoOwner, setRepoOwner] = useState("");
  const [branches, setBranches] = useState<RepositoryBranch[]>([]);
  const [rules, setRules] = useState<BranchProtectionRule[]>([]);
  const [policies, setPolicies] = useState<RepoPolicies>(DEFAULT_POLICIES);

  const [loading, setLoading] = useState(true);
  const [savingGeneral, setSavingGeneral] = useState(false);
  const [savingPolicies, setSavingPolicies] = useState(false);
  const [savingRule, setSavingRule] = useState(false);
  const [deletingRuleId, setDeletingRuleId] = useState<string | null>(null);
  const [ruleToDelete, setRuleToDelete] = useState<BranchProtectionRule | null>(null);

  // General Form
  const [editName, setEditName] = useState("");
  const [editBranch, setEditBranch] = useState("");
  const [editDesc, setEditDesc] = useState("");

  // Branch Protection Editor Modal
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<BranchProtectionRule | null>(null);

  // Branches search filter
  const [branchQuery, setBranchQuery] = useState("");

  // Danger actions
  const [dangerModal, setDangerModal] = useState<{ open: boolean; action: DangerAction }>({
    open: false,
    action: "",
  });
  const [confirmInput, setConfirmInput] = useState("");
  const [newOwnerInput, setNewOwnerInput] = useState("");
  const [newVisibility, setNewVisibility] = useState<"public" | "private">("private");
  const [executingDanger, setExecutingDanger] = useState(false);

  // Toast
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    window.setTimeout(() => {
      setToast((curr) => (curr?.msg === msg ? null : curr));
    }, 4000);
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    showToast(`Copied ${label} to clipboard`);
    window.setTimeout(() => setCopiedText(null), 2000);
  };

  const resolveRepository = async (): Promise<{ repository: Repository; owner: string }> => {
    const user = await authService.getCurrentUser();
    const allRepos = await repositoryService.listRepositories();

    const userMatch = allRepos.find(
      (candidate) =>
        candidate.name.toLowerCase() === repoParam.toLowerCase() &&
        (candidate.owner?.toLowerCase() === user.username.toLowerCase() ||
          candidate.owner_id === user.id),
    );

    const directMatch =
      userMatch ||
      allRepos.find(
        (candidate) => candidate.name.toLowerCase() === repoParam.toLowerCase(),
      );

    if (!directMatch) {
      const fallback = await repositoryService.getRepository(user.username, repoParam);
      return {
        repository: fallback,
        owner: fallback.owner || user.username,
      };
    }

    return {
      repository: directMatch,
      owner: directMatch.owner || user.username,
    };
  };

  const loadSettings = async () => {
    setLoading(true);
    try {
      if (!repoParam) throw new Error("Repository parameter missing");

      const resolved = await resolveRepository();
      const authoritative = resolved.repository;
      const owner = resolved.owner;

      const branchData = await repositoryService.getBranches(owner, authoritative.name);
      const repositoryBranches: RepositoryBranch[] = Array.isArray(branchData?.branches)
        ? branchData.branches
        : [];

      setRepo({
        ...authoritative,
        owner,
      });
      setRepoOwner(owner);
      setBranches(repositoryBranches);

      const preferredBranch =
        authoritative.default_branch ||
        branchData?.default_branch ||
        repositoryBranches[0]?.name ||
        "main";

      setEditName(authoritative.name || "");
      setEditBranch(preferredBranch);
      setEditDesc(authoritative.description || "");

      // Load repository-level policies from repository.settings
      const loadedPolicies: RepoPolicies = {
        ...DEFAULT_POLICIES,
        ...((authoritative.settings as any)?.policies || {}),
      };
      setPolicies(loadedPolicies);

      // Load branch protection rules
      const loadedRules = await branchProtectionService.list(authoritative.id);
      setRules(Array.isArray(loadedRules) ? loadedRules : []);
    } catch (err: any) {
      console.error("Failed to load repository settings:", err);
      showToast(err?.detail || err?.message || "Failed to load repository settings", false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoParam]);

  const handleSaveGeneral = async () => {
    if (!repo) return;
    const name = editName.trim();
    const description = editDesc.trim();
    const defaultBranch = editBranch.trim();

    if (!name) {
      showToast("Repository name cannot be empty", false);
      return;
    }
    if (!defaultBranch) {
      showToast("Default branch cannot be empty", false);
      return;
    }

    setSavingGeneral(true);
    try {
      const res = await repositoryService.updateSettings(repoOwner, repo.name, {
        name,
        default_branch: defaultBranch,
        description,
      });

      setRepo((curr) => (curr ? { ...curr, ...res } : curr));
      if ((res as any)?.github_sync?.notice) {
        showToast((res as any).github_sync.notice);
      } else if (repo.provider_type === "github") {
        showToast("Settings updated and synchronized with GitHub");
      } else {
        showToast("General settings updated successfully");
      }

      if (res.name && res.name !== repo.name) {
        router.replace(`/repositories/${encodeURIComponent(res.name)}/settings`);
      }
    } catch (err: any) {
      showToast(err?.detail || err?.message || "Failed to save settings", false);
    } finally {
      setSavingGeneral(false);
    }
  };

  const handleSavePolicies = async () => {
    if (!repo) return;
    setSavingPolicies(true);
    try {
      const currentSettings = repo.settings || {};
      const updatedSettings = {
        ...currentSettings,
        policies,
      };

      const res = await repositoryService.updateSettings(repoOwner, repo.name, {
        settings: updatedSettings,
      });

      setRepo((curr) => (curr ? { ...curr, settings: res.settings } : curr));
      showToast("Repository policies updated and actively enforced");
    } catch (err: any) {
      showToast(err?.detail || err?.message || "Failed to update policies", false);
    } finally {
      setSavingPolicies(false);
    }
  };

  const openNewRuleModal = () => {
    if (!repo) return;
    setEditingRule(EMPTY_RULE(repo.id, repo.default_branch || "main"));
    setRuleModalOpen(true);
  };

  const openEditRuleModal = (rule: BranchProtectionRule) => {
    setEditingRule({ ...rule });
    setRuleModalOpen(true);
  };

  const handleSaveRule = async () => {
    if (!repo || !editingRule) return;
    const branchPattern = editingRule.branch_pattern.trim();
    if (!branchPattern) {
      showToast("Branch pattern is required", false);
      return;
    }

    setSavingRule(true);
    try {
      const payload: BranchProtectionWrite = {
        branch_pattern: branchPattern,
        enabled: editingRule.enabled,
        required_approvals: Math.max(0, Number(editingRule.required_approvals) || 0),
        require_change_review: editingRule.require_change_review,
        require_clean_conflict: editingRule.require_clean_conflict,
        require_resolved_threads: editingRule.require_resolved_threads,
        require_agent_review: editingRule.require_agent_review,
        require_no_blocking_agent_findings: editingRule.require_no_blocking_agent_findings,
        allow_author_self_approval: editingRule.allow_author_self_approval,
        require_ci_passed: editingRule.require_ci_passed,
      };

      if (editingRule.id) {
        const updated = await branchProtectionService.update(repo.id, editingRule.id, payload);
        setRules((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
        showToast(`Branch rule "${branchPattern}" updated`);
      } else {
        const created = await branchProtectionService.create(repo.id, payload);
        setRules((prev) => [...prev, created]);
        showToast(`Branch rule "${branchPattern}" created`);
      }

      setRuleModalOpen(false);
      setEditingRule(null);
    } catch (err: any) {
      showToast(err?.detail || err?.message || "Failed to save rule", false);
    } finally {
      setSavingRule(false);
    }
  };

  const handleDeleteRule = (rule: BranchProtectionRule) => {
    if (!repo || !rule.id) return;
    setRuleToDelete(rule);
  };

  const confirmDeleteRule = async () => {
    if (!repo || !ruleToDelete?.id) return;
    const rule = ruleToDelete;
    setDeletingRuleId(rule.id);
    try {
      await branchProtectionService.remove(repo.id, rule.id);
      setRules((prev) => prev.filter((r) => r.id !== rule.id));
      showToast(`Rule for "${rule.branch_pattern}" deleted`);
      setRuleToDelete(null);
    } catch (err: any) {
      showToast(err?.detail || err?.message || "Failed to delete rule", false);
    } finally {
      setDeletingRuleId(null);
    }
  };

  const openDangerModal = (action: DangerAction) => {
    setConfirmInput("");
    setNewOwnerInput("");
    setNewVisibility(repo?.visibility === "private" ? "public" : "private");
    setDangerModal({ open: true, action });
  };

  const closeDangerModal = () => {
    if (executingDanger) return;
    setDangerModal({ open: false, action: "" });
    setConfirmInput("");
    setNewOwnerInput("");
  };

  const executeDangerAction = async () => {
    if (!repo || !dangerModal.action) return;
    setExecutingDanger(true);

    try {
      if (dangerModal.action === "delete") {
        await repositoryService.deleteRepository(repoOwner, repo.name);
        showToast("Repository deleted");
        closeDangerModal();
        router.replace("/repositories");
        return;
      }

      if (dangerModal.action === "visibility") {
        await repositoryService.updateVisibility(repoOwner, repo.name, newVisibility);
        setRepo((curr) =>
          curr
            ? {
                ...curr,
                visibility: newVisibility,
                is_private: newVisibility === "private",
              }
            : curr,
        );
        closeDangerModal();
        showToast(`Repository visibility changed to ${newVisibility}`);
        return;
      }

      if (dangerModal.action === "transfer") {
        const nextOwner = newOwnerInput.trim();
        await repositoryService.transferRepository(repoOwner, repo.name, nextOwner);
        closeDangerModal();
        showToast(`Repository transferred to ${nextOwner}`);
        router.replace("/repositories");
        return;
      }
    } catch (err: any) {
      showToast(err?.detail || err?.message || "Action failed", false);
    } finally {
      setExecutingDanger(false);
    }
  };

  const dangerConfirmed = useMemo(() => {
    if (!repo) return false;
    if (dangerModal.action === "delete") return confirmInput === repo.name;
    if (dangerModal.action === "visibility") return confirmInput === `make ${newVisibility}`;
    if (dangerModal.action === "transfer")
      return !!newOwnerInput.trim() && confirmInput === "transfer ownership";
    return false;
  }, [confirmInput, dangerModal.action, newOwnerInput, newVisibility, repo]);

  const filteredBranches = useMemo(() => {
    if (!branchQuery.trim()) return branches;
    return branches.filter((b) => b.name.toLowerCase().includes(branchQuery.toLowerCase()));
  }, [branches, branchQuery]);

  if (loading) {
    return <SkeletonRepoSettings />;
  }

  if (!repo) {
    return (
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 20px" }}>
        <div className="card" style={{ padding: 36, textAlign: "center" }}>
          <AlertTriangle size={36} color="var(--amber)" style={{ margin: "0 auto 16px" }} />
          <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>Repository Unavailable</h2>
          <p style={{ color: "var(--muted)", marginBottom: 24, fontSize: 14 }}>
            Could not resolve repository &ldquo;{repoParam}&rdquo;. Check your permissions or try again.
          </p>
          <button onClick={() => void loadSettings()} className="btn primary" style={{ minWidth: 120 }}>
            <RefreshCw size={15} /> Retry
          </button>
        </div>
      </div>
    );
  }

  const activePoliciesCount = Object.entries(policies).filter(
    ([k, v]) => k !== "min_approvals" && Boolean(v),
  ).length;

  return (
    <div style={{ width: "100%" }}>
      {/* Page Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--muted)", marginBottom: 6 }}>
          <Link href="/repositories" style={{ color: "var(--muted)", textDecoration: "none" }}>
            Repositories
          </Link>
          <span>/</span>
          <Link href={`/repositories/${encodeURIComponent(repo.name)}`} style={{ color: "var(--muted)", textDecoration: "none" }}>
            {repoOwner}
          </Link>
          <span>/</span>
          <span style={{ color: "var(--fg)", fontWeight: 600 }}>{repo.name}</span>
          <span>/</span>
          <span style={{ color: "var(--cyan)" }}>Settings</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 10,
                  background: "linear-gradient(135deg, rgba(92, 200, 232, 0.16), rgba(167, 139, 250, 0.16))",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  display: "grid",
                  placeItems: "center",
                  color: "var(--cyan)",
                }}
              >
                <Sliders size={20} />
              </div>
              <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>
                Repository Settings
              </h1>
            </div>
            <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
              Configure identity, governance policies, branch protection gates, and repository lifecycle.
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {repo.provider_type === "github" && (
              <a
                href={`https://github.com/${repo.provider_owner || repoOwner}/${repo.name}`}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  fontSize: 12,
                  fontWeight: 600,
                  padding: "4px 10px",
                  borderRadius: 9999,
                  background: "rgba(92, 200, 232, 0.12)",
                  color: "var(--cyan)",
                  border: "1px solid rgba(92, 200, 232, 0.25)",
                  textDecoration: "none",
                }}
              >
                <ExternalLink size={12} />
                GitHub: {repo.provider_owner || repoOwner}/{repo.name}
              </a>
            )}

            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                fontSize: 12,
                fontWeight: 600,
                padding: "4px 10px",
                borderRadius: 9999,
                background: repo.visibility === "private" ? "rgba(167, 139, 250, 0.12)" : "rgba(34, 197, 94, 0.12)",
                color: repo.visibility === "private" ? "var(--violet)" : "var(--green)",
                border: `1px solid ${repo.visibility === "private" ? "rgba(167, 139, 250, 0.25)" : "rgba(34, 197, 94, 0.25)"}`,
              }}
            >
              {repo.visibility === "private" ? <Lock size={12} /> : <Unlock size={12} />}
              {repo.visibility.toUpperCase()}
            </span>

            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                fontSize: 12,
                fontWeight: 500,
                padding: "4px 10px",
                borderRadius: 9999,
                background: "rgba(255, 255, 255, 0.05)",
                color: "var(--text-secondary)",
                border: "1px solid var(--line)",
              }}
            >
              <GitBranch size={12} />
              {repo.default_branch}
            </span>
          </div>
        </div>
      </div>

      {/* Modern Navigation Tabs */}
      <div
        style={{
          display: "flex",
          gap: 6,
          borderBottom: "1px solid var(--line)",
          paddingBottom: 2,
          marginBottom: 28,
          overflowX: "auto",
        }}
      >
        <button
          onClick={() => setActiveTab("general")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 16px",
            fontSize: 13,
            fontWeight: 600,
            borderRadius: "8px 8px 0 0",
            border: "none",
            cursor: "pointer",
            background: activeTab === "general" ? "rgba(255,255,255,0.06)" : "transparent",
            color: activeTab === "general" ? "var(--fg)" : "var(--muted)",
            borderBottom: activeTab === "general" ? "2px solid var(--cyan)" : "2px solid transparent",
            transition: "all 0.2s ease",
          }}
        >
          <Sliders size={15} />
          General
        </button>

        <button
          onClick={() => setActiveTab("policies")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 16px",
            fontSize: 13,
            fontWeight: 600,
            borderRadius: "8px 8px 0 0",
            border: "none",
            cursor: "pointer",
            background: activeTab === "policies" ? "rgba(255,255,255,0.06)" : "transparent",
            color: activeTab === "policies" ? "var(--fg)" : "var(--muted)",
            borderBottom: activeTab === "policies" ? "2px solid var(--cyan)" : "2px solid transparent",
            transition: "all 0.2s ease",
          }}
        >
          <ShieldCheck size={15} />
          Policies & Protection
          <span
            style={{
              fontSize: 11,
              padding: "1px 6px",
              borderRadius: 10,
              background: activePoliciesCount > 0 ? "rgba(92, 200, 232, 0.18)" : "rgba(255,255,255,0.08)",
              color: activePoliciesCount > 0 ? "var(--cyan)" : "var(--muted)",
              fontWeight: 700,
            }}
          >
            {activePoliciesCount}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("branches")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 16px",
            fontSize: 13,
            fontWeight: 600,
            borderRadius: "8px 8px 0 0",
            border: "none",
            cursor: "pointer",
            background: activeTab === "branches" ? "rgba(255,255,255,0.06)" : "transparent",
            color: activeTab === "branches" ? "var(--fg)" : "var(--muted)",
            borderBottom: activeTab === "branches" ? "2px solid var(--cyan)" : "2px solid transparent",
            transition: "all 0.2s ease",
          }}
        >
          <GitBranch size={15} />
          Branches
          <span
            style={{
              fontSize: 11,
              padding: "1px 6px",
              borderRadius: 10,
              background: "rgba(255,255,255,0.08)",
              color: "var(--muted)",
              fontWeight: 700,
            }}
          >
            {branches.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab("danger")}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "9px 16px",
            fontSize: 13,
            fontWeight: 600,
            borderRadius: "8px 8px 0 0",
            border: "none",
            cursor: "pointer",
            background: activeTab === "danger" ? "rgba(239, 68, 68, 0.08)" : "transparent",
            color: activeTab === "danger" ? "var(--red)" : "var(--muted)",
            borderBottom: activeTab === "danger" ? "2px solid var(--red)" : "2px solid transparent",
            transition: "all 0.2s ease",
            marginLeft: "auto",
          }}
        >
          <AlertTriangle size={15} />
          Danger Zone
        </button>
      </div>

      {/* TAB 1: GENERAL SETTINGS */}
      {activeTab === "general" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* GitHub Connection Banner (when provider is GitHub) */}
          {repo.provider_type === "github" && (
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                gap: 16,
                padding: "16px 20px",
                borderRadius: 14,
                background: "rgba(92, 200, 232, 0.05)",
                border: "1px solid rgba(92, 200, 232, 0.2)",
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                <div style={{ color: "var(--cyan)", marginTop: 2 }}>
                  <Workflow size={20} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>
                    GitHub Integrated Repository
                  </div>
                  <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 3, maxWidth: 540, lineHeight: 1.5 }}>
                    Connected upstream to{" "}
                    <a
                      href={`https://github.com/${repo.provider_owner || repoOwner}/${repo.name}`}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: "var(--cyan)", textDecoration: "underline", fontWeight: 600 }}
                    >
                      {repo.provider_owner || repoOwner}/{repo.name}
                    </a>
                    . Changes to default branch, name, description, and visibility actively synchronize with your GitHub repository.
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <a
                  href={`https://github.com/${repo.provider_owner || repoOwner}/${repo.name}/settings`}
                  target="_blank"
                  rel="noreferrer"
                  className="btn outline"
                  style={{
                    height: 32,
                    padding: "0 12px",
                    fontSize: 12,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    borderColor: "rgba(92, 200, 232, 0.3)",
                    color: "var(--cyan)",
                    fontWeight: 600,
                  }}
                >
                  GitHub Settings <ExternalLink size={12} />
                </a>
              </div>
            </div>
          )}

          {/* Identity & Metadata Card */}
          <div
            className="card"
            style={{
              borderRadius: 16,
              border: "1px solid var(--line)",
              background: "var(--card)",
              padding: 24,
            }}
          >
            <div style={{ borderBottom: "1px solid var(--line)", paddingBottom: 16, marginBottom: 20 }}>
              <h2 style={{ fontSize: 16, fontWeight: 600 }}>Repository Details</h2>
              <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
                Primary metadata and repository naming configuration.
              </p>
            </div>

            <div style={{ display: "grid", gap: 18, maxWidth: 650 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>
                  Repository Name
                </label>
                <input
                  type="text"
                  className="input"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  disabled={savingGeneral}
                  style={{ width: "100%", height: 38, fontSize: 14 }}
                />
                <p style={{ color: "var(--muted)", fontSize: 11, marginTop: 4 }}>
                  Changing the repository name will update the URL slug.
                </p>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>
                  Description
                </label>
                <textarea
                  className="input"
                  rows={3}
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  disabled={savingGeneral}
                  placeholder="Short description of this project"
                  style={{ width: "100%", fontSize: 13, resize: "vertical", padding: "8px 12px" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>
                  Default Branch
                </label>
                <select
                  className="input"
                  value={editBranch}
                  onChange={(e) => setEditBranch(e.target.value)}
                  disabled={savingGeneral}
                  style={{ width: "100%", height: 38, fontSize: 14 }}
                >
                  {branches.map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name}
                    </option>
                  ))}
                  {!branches.some((b) => b.name === editBranch) && (
                    <option value={editBranch}>{editBranch}</option>
                  )}
                </select>
                <p style={{ color: "var(--muted)", fontSize: 11, marginTop: 4 }}>
                  The default branch for pull requests, tasks, and initial code views.
                </p>
              </div>

              <div style={{ paddingTop: 8 }}>
                <button
                  type="button"
                  onClick={handleSaveGeneral}
                  disabled={savingGeneral}
                  className="btn primary"
                  style={{
                    height: 36,
                    padding: "0 20px",
                    fontWeight: 600,
                    fontSize: 13,
                    borderRadius: 8,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  {savingGeneral ? <RefreshCw size={14} className="spin" /> : <Check size={14} />}
                  Save General Settings
                </button>
              </div>
            </div>
          </div>

          {/* Repository Technical Identity Card */}
          <div
            className="card"
            style={{
              borderRadius: 16,
              border: "1px solid var(--line)",
              background: "var(--card)",
              padding: 24,
            }}
          >
            <div style={{ borderBottom: "1px solid var(--line)", paddingBottom: 16, marginBottom: 20 }}>
              <h2 style={{ fontSize: 16, fontWeight: 600 }}>Technical Specifications</h2>
              <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
                Substrate keys, cloning information, and internal identifier.
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
              <div style={{ padding: 14, borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)" }}>
                <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>
                  Repository ID
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--fg)" }}>{repo.id}</span>
                  <button
                    onClick={() => copyToClipboard(repo.id, "Repository ID")}
                    className="btn outline"
                    style={{ padding: "4px 8px", height: 26, fontSize: 11 }}
                    title="Copy ID"
                  >
                    <Copy size={12} />
                  </button>
                </div>
              </div>

              <div style={{ padding: 14, borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)" }}>
                <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>
                  Storage Key
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--fg)", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {(repo as any).storage_key || repo.name}
                  </span>
                  <button
                    onClick={() => copyToClipboard((repo as any).storage_key || repo.name, "Storage Key")}
                    className="btn outline"
                    style={{ padding: "4px 8px", height: 26, fontSize: 11 }}
                    title="Copy Key"
                  >
                    <Copy size={12} />
                  </button>
                </div>
              </div>

              <div style={{ padding: 14, borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)" }}>
                <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                  <GitBranch size={12} color="var(--cyan)" />
                  GitHub Clone Address (HTTPS)
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--cyan)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    https://github.com/{repo.provider_owner || repoOwner}/{repo.name}.git
                  </span>
                  <button
                    onClick={() => copyToClipboard(`https://github.com/${repo.provider_owner || repoOwner}/${repo.name}.git`, "GitHub HTTPS Clone URL")}
                    className="btn outline"
                    style={{ padding: "4px 8px", height: 26, fontSize: 11, flexShrink: 0 }}
                    title="Copy GitHub Clone URL"
                  >
                    <Copy size={12} />
                  </button>
                </div>
              </div>

              <div style={{ padding: 14, borderRadius: 10, background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)", marginTop: 10 }}>
                <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", fontWeight: 700, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                  <GitBranch size={12} color="var(--violet)" />
                  GitHub Clone Address (SSH)
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--fg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    git@github.com:{repo.provider_owner || repoOwner}/{repo.name}.git
                  </span>
                  <button
                    onClick={() => copyToClipboard(`git@github.com:${repo.provider_owner || repoOwner}/${repo.name}.git`, "GitHub SSH Clone URL")}
                    className="btn outline"
                    style={{ padding: "4px 8px", height: 26, fontSize: 11, flexShrink: 0 }}
                    title="Copy GitHub SSH URL"
                  >
                    <Copy size={12} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: POLICIES & BRANCH PROTECTION (CORE REQUIREMENT) */}
      {activeTab === "policies" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          {/* Hero Explainer Card */}
          <div
            style={{
              borderRadius: 16,
              padding: "20px 24px",
              background: "linear-gradient(135deg, rgba(92, 200, 232, 0.08) 0%, rgba(167, 139, 250, 0.08) 100%)",
              border: "1px solid rgba(92, 200, 232, 0.2)",
              display: "flex",
              alignItems: "flex-start",
              gap: 16,
            }}
          >
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: "rgba(92, 200, 232, 0.15)",
                display: "grid",
                placeItems: "center",
                color: "var(--cyan)",
                flexShrink: 0,
              }}
            >
              <ShieldCheck size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--fg)" }}>
                Enforced Control-Plane Governance Policies
              </h3>
              <p style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4, lineHeight: 1.5 }}>
                Policies configured here are <strong>strictly evaluated by the backend</strong> whenever an AI agent,
                developer, or external tool creates a pull request, pushes commits, or requests a merge.
                Violations immediately block PR submission or merge progression.
              </p>
            </div>
          </div>

          {/* Section A: Pull Request Submission Policies */}
          <div
            className="card"
            style={{
              borderRadius: 16,
              border: "1px solid var(--line)",
              background: "var(--card)",
              padding: 24,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, borderBottom: "1px solid var(--line)", paddingBottom: 16, marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 600 }}>Pull Request Submission & Merge Policies</h2>
                <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
                  Repository-wide requirements enforced on every Pull Request.
                </p>
              </div>

              <button
                type="button"
                onClick={handleSavePolicies}
                disabled={savingPolicies}
                className="btn primary"
                style={{
                  height: 36,
                  padding: "0 18px",
                  fontWeight: 600,
                  fontSize: 13,
                  borderRadius: 8,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                {savingPolicies ? <RefreshCw size={14} className="spin" /> : <Check size={14} />}
                Save Policy Configuration
              </button>
            </div>

            <div style={{ display: "grid", gap: 14 }}>
              {/* Policy 1: Require Task Linkage */}
              <PolicyToggleItem
                icon={<ListTodo size={18} />}
                title="Require SUTRA Task Linkage"
                description="All pull requests must be explicitly linked to a tracked SUTRA Task. Blocks unlinked agent PRs and rogue commits."
                checked={Boolean(policies.require_task_linkage)}
                onChange={(checked) => setPolicies((p) => ({ ...p, require_task_linkage: checked }))}
                badgeTone="aqua"
                badgeLabel="Agent & Human PR Gate"
              />

              {/* Policy 2: Enforce Governed Provenance */}
              <PolicyToggleItem
                icon={<ShieldCheck size={18} />}
                title="Enforce Governed Provenance"
                description="Rejects unverified or external commits without verifiable SUTRA author/agent cryptographic provenance."
                checked={Boolean(policies.enforce_governed_provenance)}
                onChange={(checked) => setPolicies((p) => ({ ...p, enforce_governed_provenance: checked }))}
                badgeTone="violet"
                badgeLabel="Integrity Gate"
              />

              {/* Policy 3: Block Merge Conflicts */}
              <PolicyToggleItem
                icon={<GitMerge size={18} />}
                title="Require Clean Conflicts on PR Creation"
                description="Automatically blocks opening or progressing PRs that have merge conflicts against the target branch."
                checked={Boolean(policies.require_clean_conflict)}
                onChange={(checked) => setPolicies((p) => ({ ...p, require_clean_conflict: checked }))}
                badgeTone="amber"
                badgeLabel="Merge Safety"
              />

              {/* Policy 4: Require Passing CI Checks */}
              <PolicyToggleItem
                icon={<Workflow size={18} />}
                title="Require Passing Automated CI Checks"
                description="All CI workflow suites and test jobs must pass cleanly before any PR can be merged."
                checked={Boolean(policies.require_ci_passed)}
                onChange={(checked) => setPolicies((p) => ({ ...p, require_ci_passed: checked }))}
                badgeTone="green"
                badgeLabel="Automated Quality"
              />

              {/* Policy 5: Require Agent Review */}
              <PolicyToggleItem
                icon={<Bot size={18} />}
                title="Require AI Agent Review & Audit"
                description="Mandates an automated review and security audit by SUTRA agents prior to human review or merge."
                checked={Boolean(policies.require_agent_review)}
                onChange={(checked) => setPolicies((p) => ({ ...p, require_agent_review: checked }))}
                badgeTone="violet"
                badgeLabel="Intelligence Audit"
              />

              {/* Policy 6: Block on Agent Findings */}
              <PolicyToggleItem
                icon={<AlertTriangle size={18} />}
                title="Block on High / Critical Agent Findings"
                description="Prohibits approval if SUTRA agent audit detects unresolved critical or high-severity vulnerabilities."
                checked={Boolean(policies.require_no_blocking_findings)}
                onChange={(checked) => setPolicies((p) => ({ ...p, require_no_blocking_findings: checked }))}
                badgeTone="red"
                badgeLabel="Security Blocker"
              />

              {/* Policy 7: Disallow Self-Approval */}
              <PolicyToggleItem
                icon={<Users size={18} />}
                title="Strict Separation of Author & Approver"
                description="Strictly forbids authors and agents from approving their own pull requests or reviews."
                checked={Boolean(policies.disallow_self_approval)}
                onChange={(checked) => setPolicies((p) => ({ ...p, disallow_self_approval: checked }))}
                badgeTone="green"
                badgeLabel="Compliance"
              />

              {/* Policy 8: Minimum Approvals Stepper */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "14px 18px",
                  borderRadius: 12,
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid var(--line)",
                  flexWrap: "wrap",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
                  <div style={{ color: "var(--cyan)", marginTop: 2 }}>
                    <CheckCircle2 size={18} />
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>
                      Minimum Required Approvals
                    </div>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                      Minimum number of peer review approvals required to permit a pull request merge.
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {[1, 2, 3].map((num) => (
                    <button
                      key={num}
                      type="button"
                      onClick={() => setPolicies((p) => ({ ...p, min_approvals: num }))}
                      style={{
                        width: 38,
                        height: 34,
                        borderRadius: 8,
                        fontSize: 13,
                        fontWeight: 700,
                        border: "1px solid",
                        borderColor: (policies.min_approvals || 1) === num ? "var(--cyan)" : "var(--line)",
                        background: (policies.min_approvals || 1) === num ? "rgba(92, 200, 232, 0.15)" : "transparent",
                        color: (policies.min_approvals || 1) === num ? "var(--cyan)" : "var(--muted)",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      {num}
                    </button>
                  ))}
                  <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 4 }}>approval(s)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Section B: Branch Protection Rules */}
          <div
            className="card"
            style={{
              borderRadius: 16,
              border: "1px solid var(--line)",
              background: "var(--card)",
              padding: 24,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, borderBottom: "1px solid var(--line)", paddingBottom: 16, marginBottom: 20 }}>
              <div>
                <h2 style={{ fontSize: 16, fontWeight: 600 }}>Branch Protection Rules</h2>
                <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
                  Fine-grained branch gating for <code>main</code>, <code>release/*</code>, and other branches.
                </p>
              </div>

              <button
                type="button"
                onClick={openNewRuleModal}
                className="btn primary"
                style={{
                  height: 36,
                  padding: "0 16px",
                  fontWeight: 600,
                  fontSize: 13,
                  borderRadius: 8,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <Plus size={15} />
                Add Protection Rule
              </button>
            </div>

            {rules.length === 0 ? (
              <div
                style={{
                  padding: "36px 20px",
                  textAlign: "center",
                  background: "rgba(255,255,255,0.01)",
                  borderRadius: 12,
                  border: "1px dashed var(--line)",
                }}
              >
                <Shield size={32} color="var(--muted)" style={{ margin: "0 auto 12px", opacity: 0.6 }} />
                <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--fg)" }}>No Branch Protection Rules</h3>
                <p style={{ fontSize: 13, color: "var(--muted)", maxWidth: 440, margin: "6px auto 18px" }}>
                  Protect your default branch ({repo.default_branch}) against unreviewed agent or human merges.
                </p>
                <button onClick={openNewRuleModal} className="btn outline" style={{ fontSize: 13 }}>
                  <Plus size={14} /> Create Rule for &ldquo;{repo.default_branch}&rdquo;
                </button>
              </div>
            ) : (
              <div style={{ display: "grid", gap: 14 }}>
                {rules.map((rule) => (
                  <div
                    key={rule.id}
                    style={{
                      borderRadius: 12,
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid var(--line)",
                      padding: "16px 20px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12, marginBottom: 12 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <code
                          style={{
                            fontSize: 14,
                            fontWeight: 700,
                            padding: "4px 10px",
                            borderRadius: 6,
                            background: "rgba(92, 200, 232, 0.12)",
                            color: "var(--cyan)",
                            border: "1px solid rgba(92, 200, 232, 0.25)",
                          }}
                        >
                          {rule.branch_pattern}
                        </code>

                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            padding: "2px 8px",
                            borderRadius: 9999,
                            background: rule.enabled ? "rgba(34, 197, 94, 0.12)" : "rgba(245, 158, 11, 0.12)",
                            color: rule.enabled ? "var(--green)" : "var(--amber)",
                            border: `1px solid ${rule.enabled ? "rgba(34, 197, 94, 0.25)" : "rgba(245, 158, 11, 0.25)"}`,
                          }}
                        >
                          {rule.enabled ? "Active" : "Disabled"}
                        </span>

                        <span style={{ fontSize: 12, color: "var(--muted)" }}>
                          {rule.required_approvals} approval{rule.required_approvals === 1 ? "" : "s"} required
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <button
                          onClick={() => openEditRuleModal(rule)}
                          className="btn outline"
                          style={{ height: 30, padding: "0 10px", fontSize: 12, display: "inline-flex", alignItems: "center", gap: 6 }}
                        >
                          <Edit3 size={12} /> Edit
                        </button>
                        <button
                          onClick={() => void handleDeleteRule(rule)}
                          disabled={deletingRuleId === rule.id}
                          className="btn outline"
                          style={{
                            height: 30,
                            padding: "0 10px",
                            fontSize: 12,
                            color: "var(--red)",
                            borderColor: "rgba(239, 68, 68, 0.3)",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                          }}
                        >
                          <Trash2 size={12} /> Delete
                        </button>
                      </div>
                    </div>

                    {/* Rule active chips */}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {rule.require_change_review && (
                        <RuleChip label="Change Review" />
                      )}
                      {rule.require_ci_passed && (
                        <RuleChip label="CI Required" />
                      )}
                      {rule.require_clean_conflict && (
                        <RuleChip label="Clean Conflicts" />
                      )}
                      {rule.require_resolved_threads && (
                        <RuleChip label="Resolved Threads" />
                      )}
                      {rule.require_agent_review && (
                        <RuleChip label="Agent Review" />
                      )}
                      {rule.require_no_blocking_agent_findings && (
                        <RuleChip label="Zero Blocking Findings" />
                      )}
                      {!rule.allow_author_self_approval && (
                        <RuleChip label="No Self-Approval" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: BRANCHES */}
      {activeTab === "branches" && (
        <div
          className="card"
          style={{
            borderRadius: 16,
            border: "1px solid var(--line)",
            background: "var(--card)",
            padding: 24,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16, borderBottom: "1px solid var(--line)", paddingBottom: 16, marginBottom: 20 }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 600 }}>Git Branches</h2>
              <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
                Current branches recorded in repository storage.
              </p>
            </div>

            <div style={{ position: "relative", width: "min(100%, 280px)" }}>
              <Search size={14} style={{ position: "absolute", left: 10, top: 11, color: "var(--muted)" }} />
              <input
                type="text"
                placeholder="Filter branches..."
                className="input"
                value={branchQuery}
                onChange={(e) => setBranchQuery(e.target.value)}
                style={{ width: "100%", height: 34, paddingLeft: 32, fontSize: 13 }}
              />
            </div>
          </div>

          {filteredBranches.length === 0 ? (
            <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
              No branches match your query.
            </div>
          ) : (
            <div style={{ display: "grid", gap: 8 }}>
              {filteredBranches.map((branch) => {
                const isDefault = branch.name === repo.default_branch;
                const isProtected = rules.some(
                  (r) => r.enabled && (r.branch_pattern === branch.name || r.branch_pattern === "*"),
                );

                return (
                  <div
                    key={branch.name}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "12px 16px",
                      borderRadius: 10,
                      background: "rgba(255,255,255,0.02)",
                      border: "1px solid var(--line)",
                      gap: 12,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <GitBranch size={16} color="var(--muted)" />
                      <span style={{ fontWeight: 600, fontSize: 14, color: "var(--fg)" }}>
                        {branch.name}
                      </span>

                      {isDefault && (
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: "2px 8px",
                            borderRadius: 9999,
                            background: "rgba(34, 197, 94, 0.12)",
                            color: "var(--green)",
                            border: "1px solid rgba(34, 197, 94, 0.25)",
                          }}
                        >
                          DEFAULT
                        </span>
                      )}

                      {isProtected && (
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: "2px 8px",
                            borderRadius: 9999,
                            background: "rgba(167, 139, 250, 0.12)",
                            color: "var(--violet)",
                            border: "1px solid rgba(167, 139, 250, 0.25)",
                          }}
                        >
                          PROTECTED
                        </span>
                      )}
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <code style={{ fontSize: 12, color: "var(--muted)", fontFamily: "monospace" }}>
                        {branch.commit ? branch.commit.slice(0, 8) : ""}
                      </code>

                      <Link
                        href={`/repositories/${encodeURIComponent(repo.name)}/code?ref=${encodeURIComponent(branch.name)}`}
                        className="btn outline"
                        style={{ height: 28, padding: "0 10px", fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4 }}
                      >
                        Browse <ArrowRight size={11} />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 4: DANGER ZONE */}
      {activeTab === "danger" && (
        <div
          className="card"
          style={{
            borderRadius: 16,
            border: "1px solid rgba(239, 68, 68, 0.25)",
            background: "rgba(239, 68, 68, 0.02)",
            padding: 24,
          }}
        >
          <div style={{ borderBottom: "1px solid rgba(239, 68, 68, 0.15)", paddingBottom: 16, marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <AlertTriangle size={20} color="var(--red)" />
              <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--red)" }}>Danger Zone</h2>
            </div>
            <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
              Irreversible and sensitive operations on this repository. Proceed with extreme caution.
            </p>
          </div>

          <div style={{ display: "grid", gap: 16 }}>
            {/* Danger 1: Change Visibility */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 20px",
                borderRadius: 12,
                border: "1px solid var(--line)",
                background: "var(--card)",
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>
                  Change Repository Visibility
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                  Currently <strong>{repo.visibility.toUpperCase()}</strong>. {repo.provider_type === "github" ? "Changing visibility synchronizes with both SUTRA and your GitHub repository." : "Making this repository public allows anyone with access to view code."}
                </div>
              </div>

              <button
                onClick={() => openDangerModal("visibility")}
                className="btn outline"
                style={{ borderColor: "var(--line)", fontWeight: 600 }}
              >
                Make {repo.visibility === "private" ? "Public" : "Private"}
              </button>
            </div>

            {/* Danger 2: Transfer Ownership */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 20px",
                borderRadius: 12,
                border: "1px solid var(--line)",
                background: "var(--card)",
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>
                  Transfer Ownership
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                  {repo.provider_type === "github"
                    ? "For GitHub-connected repositories, ownership transfer is primarily managed on GitHub settings. SUTRA will synchronize the new owner."
                    : "Transfer this repository to another user or organization account."}
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {repo.provider_type === "github" && (
                  <a
                    href={`https://github.com/${repo.provider_owner || repoOwner}/${repo.name}/settings`}
                    target="_blank"
                    rel="noreferrer"
                    className="btn outline"
                    style={{ borderColor: "var(--line)", fontWeight: 600, fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4 }}
                  >
                    GitHub Settings <ExternalLink size={11} />
                  </a>
                )}
                <button
                  onClick={() => openDangerModal("transfer")}
                  className="btn outline"
                  style={{ borderColor: "var(--line)", fontWeight: 600 }}
                >
                  Transfer in SUTRA
                </button>
              </div>
            </div>

            {/* Danger 3: Delete Repository */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "16px 20px",
                borderRadius: 12,
                border: "1px solid rgba(239, 68, 68, 0.3)",
                background: "rgba(239, 68, 68, 0.04)",
                flexWrap: "wrap",
                gap: 12,
              }}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--red)" }}>
                  Delete Repository
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                  {repo.provider_type === "github"
                    ? "Soft-deletes and decouples this repository in SUTRA. If GitHub App administration permissions permit, upstream deletion is also requested."
                    : "Permanently delete this repository, branch rules, and on-disk Git storage. There is no recovery."}
                </div>
              </div>

              <button
                onClick={() => openDangerModal("delete")}
                className="btn primary"
                style={{ background: "var(--red)", borderColor: "var(--red)", fontWeight: 700 }}
              >
                Delete This Repository
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Branch Protection Rule Editor */}
      {ruleModalOpen && editingRule && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.7)",
            backdropFilter: "blur(6px)",
            display: "grid",
            placeItems: "center",
            zIndex: 1000,
            padding: 16,
          }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget && !savingRule) {
              setRuleModalOpen(false);
            }
          }}
        >
          <div
            className="card"
            style={{
              width: "min(100%, 580px)",
              maxHeight: "90vh",
              overflowY: "auto",
              borderRadius: 16,
              background: "var(--surface)",
              border: "1px solid var(--line)",
              boxShadow: "0 24px 48px rgba(0, 0, 0, 0.5)",
              padding: 24,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: 16, marginBottom: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <ShieldCheck size={20} color="var(--cyan)" />
                <h3 style={{ fontSize: 17, fontWeight: 700 }}>
                  {editingRule.id ? "Edit Branch Protection Rule" : "New Branch Protection Rule"}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setRuleModalOpen(false)}
                disabled={savingRule}
                className="btn outline"
                style={{ padding: "4px 8px", height: 28 }}
              >
                <X size={15} />
              </button>
            </div>

            <div style={{ display: "grid", gap: 16 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>
                  Branch Name or Glob Pattern
                </label>
                <input
                  type="text"
                  className="input"
                  value={editingRule.branch_pattern}
                  onChange={(e) => setEditingRule({ ...editingRule, branch_pattern: e.target.value })}
                  placeholder="e.g. main, release/*, *"
                  style={{ width: "100%", height: 38 }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--text-secondary)", marginBottom: 6 }}>
                  Required Peer Approvals
                </label>
                <input
                  type="number"
                  min={0}
                  step={1}
                  className="input"
                  value={editingRule.required_approvals}
                  onChange={(e) =>
                    setEditingRule({
                      ...editingRule,
                      required_approvals: Math.max(0, parseInt(e.target.value, 10) || 0),
                    })
                  }
                  style={{ width: "100%", height: 38 }}
                />
              </div>

              {/* Rule Gates Toggles */}
              <div style={{ display: "grid", gap: 10, marginTop: 4 }}>
                <ModalSwitchItem
                  label="Rule Enabled"
                  description="Activate this rule on matching branches"
                  checked={editingRule.enabled}
                  onChange={(checked) => setEditingRule({ ...editingRule, enabled: checked })}
                />

                <ModalSwitchItem
                  label="Require Change Review"
                  description="Enforces formal SUTRA Change review specification"
                  checked={editingRule.require_change_review}
                  onChange={(checked) => setEditingRule({ ...editingRule, require_change_review: checked })}
                />

                <ModalSwitchItem
                  label="Require Clean Conflicts"
                  description="Blocks PR if Git conflicts exist with target branch"
                  checked={editingRule.require_clean_conflict}
                  onChange={(checked) => setEditingRule({ ...editingRule, require_clean_conflict: checked })}
                />

                <ModalSwitchItem
                  label="Require Resolved Review Threads"
                  description="All inline review discussions must be marked resolved"
                  checked={editingRule.require_resolved_threads}
                  onChange={(checked) => setEditingRule({ ...editingRule, require_resolved_threads: checked })}
                />

                <ModalSwitchItem
                  label="Require AI Agent Review"
                  description="Requires automated agent audit participation"
                  checked={editingRule.require_agent_review}
                  onChange={(checked) => setEditingRule({ ...editingRule, require_agent_review: checked })}
                />

                <ModalSwitchItem
                  label="Block on Agent Findings"
                  description="Blocks PR if agents report critical or high severity issues"
                  checked={editingRule.require_no_blocking_agent_findings}
                  onChange={(checked) =>
                    setEditingRule({ ...editingRule, require_no_blocking_agent_findings: checked })
                  }
                />

                <ModalSwitchItem
                  label="Require Automated CI Checks to Pass"
                  description="PR cannot merge unless CI test workflow succeeds"
                  checked={editingRule.require_ci_passed}
                  onChange={(checked) => setEditingRule({ ...editingRule, require_ci_passed: checked })}
                />

                <ModalSwitchItem
                  label="Allow Author Self-Approval"
                  description="Not recommended: permits PR authors to approve their own PR"
                  checked={editingRule.allow_author_self_approval}
                  onChange={(checked) =>
                    setEditingRule({ ...editingRule, allow_author_self_approval: checked })
                  }
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
                <button
                  type="button"
                  onClick={() => setRuleModalOpen(false)}
                  disabled={savingRule}
                  className="btn outline"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveRule}
                  disabled={savingRule}
                  className="btn primary"
                  style={{ minWidth: 120 }}
                >
                  {savingRule ? <RefreshCw size={14} className="spin" /> : <Check size={14} />}
                  {editingRule.id ? "Save Changes" : "Create Rule"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: Danger Action Confirmation */}
      {dangerModal.open && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(8px)",
            display: "grid",
            placeItems: "center",
            zIndex: 1000,
            padding: 16,
          }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget && !executingDanger) {
              closeDangerModal();
            }
          }}
        >
          <div
            className="card"
            style={{
              width: "min(100%, 480px)",
              borderRadius: 16,
              background: "var(--surface)",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              boxShadow: "0 24px 48px rgba(0, 0, 0, 0.6)",
              padding: 24,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--line)", paddingBottom: 14, marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <AlertTriangle size={20} color="var(--red)" />
                <h3 style={{ fontSize: 17, fontWeight: 700, color: "var(--red)" }}>
                  {dangerModal.action === "delete" && "Delete Repository"}
                  {dangerModal.action === "visibility" && "Change Visibility"}
                  {dangerModal.action === "transfer" && "Transfer Repository"}
                </h3>
              </div>
              <button
                type="button"
                onClick={closeDangerModal}
                disabled={executingDanger}
                className="btn outline"
                style={{ padding: "4px 8px", height: 28 }}
              >
                <X size={15} />
              </button>
            </div>

            <div style={{ display: "grid", gap: 16 }}>
              {dangerModal.action === "delete" && (
                <>
                  <p style={{ color: "var(--text-secondary)", fontSize: 13, lineHeight: 1.5 }}>
                    This action will permanently remove <strong>{repo.name}</strong>, all branch protection rules,
                    and its backing Git repository from SUTRA.
                  </p>
                  <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--muted)", marginBottom: 6 }}>
                      Type <code>{repo.name}</code> to confirm:
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={confirmInput}
                      onChange={(e) => setConfirmInput(e.target.value)}
                      placeholder={repo.name}
                      style={{ width: "100%", height: 38 }}
                    />
                  </div>
                </>
              )}

              {dangerModal.action === "visibility" && (
                <>
                  <p style={{ color: "var(--text-secondary)", fontSize: 13, lineHeight: 1.5 }}>
                    Change repository visibility to <strong>{newVisibility.toUpperCase()}</strong>.
                  </p>
                  <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--muted)", marginBottom: 6 }}>
                      Type <code>make {newVisibility}</code> to confirm:
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={confirmInput}
                      onChange={(e) => setConfirmInput(e.target.value)}
                      placeholder={`make ${newVisibility}`}
                      style={{ width: "100%", height: 38 }}
                    />
                  </div>
                </>
              )}

              {dangerModal.action === "transfer" && (
                <>
                  <p style={{ color: "var(--text-secondary)", fontSize: 13, lineHeight: 1.5 }}>
                    Transfer this repository to another valid username or organization.
                  </p>
                  <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--muted)", marginBottom: 6 }}>
                      New Owner Username
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={newOwnerInput}
                      onChange={(e) => setNewOwnerInput(e.target.value)}
                      placeholder="e.g. org-lead"
                      style={{ width: "100%", height: 38, marginBottom: 12 }}
                    />
                    <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--muted)", marginBottom: 6 }}>
                      Type <code>transfer ownership</code> to confirm:
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={confirmInput}
                      onChange={(e) => setConfirmInput(e.target.value)}
                      placeholder="transfer ownership"
                      style={{ width: "100%", height: 38 }}
                    />
                  </div>
                </>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={closeDangerModal}
                  disabled={executingDanger}
                  className="btn outline"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={executeDangerAction}
                  disabled={!dangerConfirmed || executingDanger}
                  className="btn primary"
                  style={{
                    background: "var(--red)",
                    borderColor: "var(--red)",
                    opacity: dangerConfirmed ? 1 : 0.4,
                  }}
                >
                  {executingDanger ? <RefreshCw size={14} className="spin" /> : <AlertTriangle size={14} />}
                  Confirm & Execute
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Toast */}
      {toast && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            right: 24,
            zIndex: 2000,
            borderRadius: 12,
            background: toast.ok ? "var(--surface-2)" : "rgba(45, 15, 18, 0.95)",
            border: `1px solid ${toast.ok ? "var(--line)" : "rgba(239, 68, 68, 0.5)"}`,
            padding: "12px 18px",
            boxShadow: "0 12px 32px rgba(0, 0, 0, 0.45)",
            display: "flex",
            alignItems: "center",
            gap: 10,
            maxWidth: 420,
            fontSize: 13,
            fontWeight: 500,
            color: "var(--fg)",
            animation: "fadeIn 0.2s ease",
          }}
        >
          {toast.ok ? <CheckCircle2 size={16} color="var(--green)" /> : <AlertTriangle size={16} color="var(--red)" />}
          <span>{toast.msg}</span>
        </div>
      )}

      <ConfirmModal
        isOpen={Boolean(ruleToDelete)}
        onClose={() => setRuleToDelete(null)}
        onConfirm={confirmDeleteRule}
        title="Delete Branch Protection Rule"
        description={
          <>
            Are you sure you want to delete the branch protection rule for <strong>&ldquo;{ruleToDelete?.branch_pattern}&rdquo;</strong>? Branch policy restrictions will no longer be enforced on matching branches.
          </>
        }
        confirmText="Delete Rule"
        confirmTone="danger"
        loading={Boolean(deletingRuleId)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper Subcomponents
// ---------------------------------------------------------------------------

function PolicyToggleItem({
  icon,
  title,
  description,
  checked,
  onChange,
  badgeTone = "aqua",
  badgeLabel,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  badgeTone?: "aqua" | "violet" | "green" | "amber" | "red";
  badgeLabel?: string;
}) {
  const toneColors: Record<string, { bg: string; text: string; border: string }> = {
    aqua: { bg: "rgba(92, 200, 232, 0.12)", text: "var(--cyan)", border: "rgba(92, 200, 232, 0.25)" },
    violet: { bg: "rgba(167, 139, 250, 0.12)", text: "var(--violet)", border: "rgba(167, 139, 250, 0.25)" },
    green: { bg: "rgba(34, 197, 94, 0.12)", text: "var(--green)", border: "rgba(34, 197, 94, 0.25)" },
    amber: { bg: "rgba(245, 158, 11, 0.12)", text: "var(--amber)", border: "rgba(245, 158, 11, 0.25)" },
    red: { bg: "rgba(239, 68, 68, 0.12)", text: "var(--red)", border: "rgba(239, 68, 68, 0.25)" },
  };
  const tone = toneColors[badgeTone] || toneColors.aqua;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 20px",
        borderRadius: 12,
        background: checked ? "rgba(255, 255, 255, 0.03)" : "rgba(255, 255, 255, 0.015)",
        border: `1px solid ${checked ? "rgba(92, 200, 232, 0.2)" : "var(--line)"}`,
        transition: "all 0.2s ease",
        flexWrap: "wrap",
        gap: 12,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14, flex: 1, minWidth: 260 }}>
        <div
          style={{
            color: checked ? "var(--cyan)" : "var(--muted)",
            marginTop: 2,
            transition: "color 0.2s ease",
          }}
        >
          {icon}
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>{title}</span>
            {badgeLabel && (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  padding: "1px 6px",
                  borderRadius: 6,
                  background: tone.bg,
                  color: tone.text,
                  border: `1px solid ${tone.border}`,
                }}
              >
                {badgeLabel}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4, lineHeight: 1.4 }}>
            {description}
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={() => onChange(!checked)}
        style={{
          width: 44,
          height: 24,
          borderRadius: 12,
          background: checked ? "var(--cyan)" : "rgba(255, 255, 255, 0.12)",
          border: "none",
          position: "relative",
          cursor: "pointer",
          transition: "background 0.2s ease",
          flexShrink: 0,
        }}
        aria-checked={checked}
        role="switch"
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: checked ? 22 : 2,
            width: 20,
            height: 20,
            borderRadius: "50%",
            background: "#fff",
            transition: "left 0.2s ease",
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.4)",
          }}
        />
      </button>
    </div>
  );
}

function ModalSwitchItem({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 14px",
        borderRadius: 8,
        background: "rgba(255, 255, 255, 0.02)",
        border: "1px solid var(--line)",
        gap: 12,
      }}
    >
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)" }}>{label}</div>
        <div style={{ fontSize: 11, color: "var(--muted)" }}>{description}</div>
      </div>

      <button
        type="button"
        onClick={() => onChange(!checked)}
        style={{
          width: 38,
          height: 20,
          borderRadius: 10,
          background: checked ? "var(--cyan)" : "rgba(255, 255, 255, 0.12)",
          border: "none",
          position: "relative",
          cursor: "pointer",
          transition: "background 0.2s ease",
          flexShrink: 0,
        }}
        aria-checked={checked}
        role="switch"
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: checked ? 20 : 2,
            width: 16,
            height: 16,
            borderRadius: "50%",
            background: "#fff",
            transition: "left 0.2s ease",
          }}
        />
      </button>
    </div>
  );
}

function RuleChip({ label }: { label: string }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 11,
        padding: "3px 8px",
        borderRadius: 6,
        background: "rgba(255, 255, 255, 0.04)",
        border: "1px solid var(--line)",
        color: "var(--text-secondary)",
      }}
    >
      <Check size={10} color="var(--cyan)" />
      {label}
    </span>
  );
}
