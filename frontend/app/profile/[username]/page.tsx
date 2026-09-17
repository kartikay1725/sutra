import Link from "next/link";
import { Page } from "@/components/ui";
import { profileService } from "@/lib/profiles";
import { FollowButton } from "@/components/FollowButton";
import { ShareProfileButton } from "@/components/ShareProfileButton";
import {
  ArrowUpRight,
  Code2,
  GitPullRequest,
  CircleDot,
  GitBranch,
  Users,
  CalendarDays,
  Copy,
  Sparkles,
  ExternalLink,
} from "lucide-react";

import {
  Github,
  Linkedin,
  Twitter,
  Instagram,
  Youtube,
  Globe,
  MessageCircle,
} from "lucide-react";

// Always SSR — contribution data is real-time and user-specific.
// Without this Next.js may statically cache the first render.
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{
    username: string;
  }>;
}

function formatDate(value?: string) {
  if (!value) return "Unknown";

  return new Date(value).toLocaleDateString(
    undefined,
    {
      year: "numeric",
      month: "long",
    },
  );
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

/**
 * Maps a contribution count to a visual intensity color.
 * Uses logarithmic scaling so gradients are meaningful across
 * the typical GitHub range of 1–30+ contributions per day.
 */
function contributionTone(count: number, maxCount = 30): string {
  if (count <= 0) {
    return "rgba(255,255,255,.045)";
  }

  // Clamp and normalize on a log scale (same approach GitHub uses)
  const effectiveMax = Math.max(maxCount, count, 10);
  const ratio = Math.log1p(count) / Math.log1p(effectiveMax);

  if (ratio < 0.25) return "rgba(34,211,238,.22)";
  if (ratio < 0.50) return "rgba(34,211,238,.42)";
  if (ratio < 0.75) return "rgba(34,211,238,.66)";
  return "#22d3ee";
}


export default async function PublicProfile({
  params,
}: PageProps) {
  const { username } = await params;

  const [profile, contributions] =
    await Promise.all([
      profileService.getProfile(username),
      profileService.getContributions(username),
    ]);

  const displayName =
    profile.full_name ||
    profile.username;

  const publicRepos =
    profile.repositories || [];

  return (
    <>
      <div className="public-profile">
        {/* Top identity */}
        <section className="profile-hero">
          <div className="profile-hero-inner">
            <div className="profile-avatar">
              {initials(displayName)}
            </div>

            <div className="profile-identity">
              <div className="profile-kicker">
                {profile.type === "organization"
                  ? "ORGANIZATION"
                  : "DEVELOPER"}
              </div>

              <h1>{displayName}</h1>

              <div className="profile-handle">
                @{profile.username}
              </div>

              <p>
                {profile.bio ||
                  "Building software, shipping ideas, and contributing to engineering projects."}
              </p>

              <div className="profile-meta">
                <span>
                  <CalendarDays size={14} />
                  Joined{" "}
                  {formatDate(
                    profile.created_at,
                  )}
                </span>

                <span>
                  <Users size={14} />
                  {profile.followers ?? 0} followers
                </span>

                <span>
                  {profile.public_repository_count}{" "}
                  public repositories
                </span>
              </div>
              {Object.keys(profile.social_links || {}).length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 8,
                    marginTop: 16,
                  }}
                >
                  {[
                    ["github", Github, "GitHub"],
                    ["linkedin", Linkedin, "LinkedIn"],
                    ["x", Twitter, "X"],
                    ["instagram", Instagram, "Instagram"],
                    ["reddit", MessageCircle, "Reddit"],
                    ["youtube", Youtube, "YouTube"],
                    ["website", Globe, "Website"],
                  ].map(([key, Icon, label]) => {
                    const href =
                      profile.social_links?.[
                        key as keyof typeof profile.social_links
                      ];

                    if (!href) return null;

                    return (
                      <a
                        key={String(key)}
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          height: 32,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 7,
                          padding: "0 10px",
                          borderRadius: 9,
                          border:
                            "1px solid rgba(255,255,255,.08)",
                          background:
                            "rgba(255,255,255,.025)",
                          color: "var(--muted)",
                          fontSize: 11,
                        }}
                      >
                        <Icon size={14} />
                        {String(label)}
                        <ExternalLink size={11} />
                      </a>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="profile-actions">
              <FollowButton
                username={profile.username}
              />

              <ShareProfileButton
                username={profile.username}
              />
            </div>
          </div>
        </section>

        {/* Main content */}
        <main className="profile-content">
          {/* Stats */}
          <section className="profile-stats">
            <div>
              <span>Public work</span>
              <strong>
                {profile.public_repository_count}
              </strong>
              <small>repositories</small>
            </div>

            <div>
              <span>Contributions</span>
              <strong>
                {contributions.total_contributions}
              </strong>
              <small>last 365 days</small>
            </div>

            <div>
              <span>Pull requests</span>
              <strong>
                {profile.pull_request_count}
              </strong>
              <small>created</small>
            </div>

            <div>
              <span>Issues</span>
              <strong>
                {profile.issue_count}
              </strong>
              <small>opened</small>
            </div>
          </section>

          <div className="profile-grid">
            {/* Main column */}
            <div className="profile-main">
              {/* Featured work */}
              <section className="profile-section">
                <div className="section-heading">
                  <div>
                    <div className="section-eyebrow">
                      SELECTED WORK
                    </div>
                    <h2>Public projects</h2>
                  </div>

                  <span>
                    {publicRepos.length}
                  </span>
                </div>

                {publicRepos.length === 0 ? (
                  <div className="profile-empty">
                    No public repositories yet.
                  </div>
                ) : (
                  <div className="repo-grid">
                    {publicRepos.map(
                      (repo) => (
                        <Link
                          key={repo.id}
                          href={`/repositories/${encodeURIComponent(
                            repo.name,
                          )}`}
                          className="repo-card"
                        >
                          <div className="repo-card-top">
                            <div className="repo-icon">
                              <Code2 size={17} />
                            </div>

                            <ArrowUpRight
                              size={16}
                              className="repo-arrow"
                            />
                          </div>

                          <h3>{repo.name}</h3>

                          <p>
                            {repo.description ||
                              "No description provided."}
                          </p>

                          <div className="repo-card-footer">
                            <span>
                              <span className="repo-dot" />
                              {repo.default_branch}
                            </span>

                            <span>
                              Updated{" "}
                              {new Date(
                                repo.updated_at,
                              ).toLocaleDateString(
                                undefined,
                                {
                                  month: "short",
                                  day: "numeric",
                                },
                              )}
                            </span>
                          </div>
                        </Link>
                      ),
                    )}
                  </div>
                )}
              </section>

              {/* Contribution graph */}
              <section className="profile-section">
                <div className="section-heading">
                  <div>
                    <div className="section-eyebrow">
                      ENGINEERING ACTIVITY
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <h2 style={{ margin: 0 }}>Contribution history</h2>
                      {contributions.github_synced && (
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 600,
                            color: "#22d3ee",
                            background: "rgba(34, 211, 238, 0.1)",
                            border: "1px solid rgba(34, 211, 238, 0.25)",
                            padding: "2px 8px",
                            borderRadius: 4,
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 5,
                          }}
                          title={`Synchronized with GitHub (@${contributions.github_account})`}
                        >
                          <Github size={12} />
                          GitHub Synced
                        </span>
                      )}
                    </div>
                  </div>

                  <span className="activity-total">
                    {contributions.total_contributions}{" "}
                    contributions
                  </span>
                </div>

                <div className="contribution-shell">
                  <div className="contribution-topline">
                    <span>Last 365 days</span>
                    <div className="contribution-legend">
                      <span>Less</span>
                      <i
                        style={{
                          background:
                            "rgba(255,255,255,.045)",
                        }}
                      />
                      <i
                        style={{
                          background:
                            "rgba(34,211,238,.25)",
                        }}
                      />
                      <i
                        style={{
                          background:
                            "rgba(34,211,238,.45)",
                        }}
                      />
                      <i
                        style={{
                          background:
                            "rgba(34,211,238,.68)",
                        }}
                      />
                      <i
                        style={{
                          background:
                            "#22d3ee",
                        }}
                      />
                      <span>More</span>
                    </div>
                  </div>

                  <div className="contribution-grid">
                    {(() => {
                      const maxCount = Math.max(
                        10,
                        ...contributions.days.map((d) => d.count),
                      );
                      return contributions.days.map((day) => (
                        <div
                          key={day.date}
                          title={`${day.date}: ${day.count} contribution${day.count !== 1 ? "s" : ""}`}
                          className="contribution-cell"
                          style={{
                            background: contributionTone(day.count, maxCount),
                          }}
                        />
                      ));
                    })()}
                  </div>
                </div>
              </section>

              {/* Engineering footprint */}
              <section className="profile-section">
                <div className="section-heading">
                  <div>
                    <div className="section-eyebrow">
                      ENGINEERING FOOTPRINT
                    </div>
                    <h2>Work across SUTRA</h2>
                  </div>
                </div>

                <div className="footprint-grid">
                  <div className="footprint-item">
                    <GitBranch size={18} />
                    <div>
                      <strong>
                        {contributions.total_contributions}
                      </strong>
                      <span>
                        recorded contributions
                      </span>
                    </div>
                  </div>

                  <div className="footprint-item">
                    <GitPullRequest size={18} />
                    <div>
                      <strong>
                        {profile.pull_request_count}
                      </strong>
                      <span>
                        pull requests
                      </span>
                    </div>
                  </div>

                  <div className="footprint-item">
                    <CircleDot size={18} />
                    <div>
                      <strong>
                        {profile.issue_count}
                      </strong>
                      <span>
                        issues opened
                      </span>
                    </div>
                  </div>

                  <div className="footprint-item">
                    <Sparkles size={18} />
                    <div>
                      <strong>
                        {profile.public_repository_count}
                      </strong>
                      <span>
                        public projects
                      </span>
                    </div>
                  </div>
                </div>
              </section>
            </div>

            {/* Sidebar */}
            <aside className="profile-sidebar">
              <section className="about-card">
                <div className="section-eyebrow">
                  ABOUT
                </div>

                <h2>
                  {displayName}
                </h2>

                <p>
                  {profile.bio ||
                    "A developer building and contributing to software projects through SUTRA."}
                </p>

                <div className="about-divider" />

                <div className="about-row">
                  <span>Followers</span>
                  <strong>
                    {profile.followers ?? 0}
                  </strong>
                </div>

                <div className="about-row">
                  <span>Following</span>
                  <strong>
                    {profile.following ?? 0}
                  </strong>
                </div>

                <div className="about-row">
                  <span>Member since</span>
                  <strong>
                    {formatDate(
                      profile.created_at,
                    )}
                  </strong>
                </div>
              </section>

              <section className="share-card">
                <div className="share-icon">
                  <Sparkles size={17} />
                </div>

                <strong>
                  Your engineering identity
                </strong>

                <p>
                  This profile is public and
                  designed to be shared as your
                  SUTRA engineering portfolio.
                </p>

                <div className="share-url">
                  /profile/
                  {profile.username}
                </div>
              </section>
            </aside>
          </div>
        </main>
      </div>

      <style>{`
        .public-profile {
          min-height: 100vh;
          background:
            radial-gradient(
              circle at 72% 8%,
              rgba(99,102,241,.12),
              transparent 30%
            ),
            radial-gradient(
              circle at 20% 18%,
              rgba(34,211,238,.06),
              transparent 28%
            );
        }

        .profile-hero {
          border-bottom: 1px solid var(--line);
          background:
            linear-gradient(
              180deg,
              rgba(255,255,255,.028),
              rgba(255,255,255,0)
            );
        }

        .profile-hero-inner {
          max-width: 1180px;
          margin: 0 auto;
          padding: 58px 32px 44px;
          display: flex;
          align-items: flex-start;
          gap: 24px;
        }

        .profile-avatar {
          width: 94px;
          height: 94px;
          border-radius: 24px;
          flex: 0 0 auto;
          display: grid;
          place-items: center;
          font-size: 30px;
          font-weight: 700;
          color: white;
          background:
            linear-gradient(
              135deg,
              #a855f7,
              #6366f1 55%,
              #22d3ee
            );
          box-shadow:
            0 18px 45px rgba(99,102,241,.2);
        }

        .profile-identity {
          flex: 1;
          min-width: 0;
        }

        .profile-kicker,
        .section-eyebrow {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: .16em;
          color: #a78bfa;
        }

        .profile-identity h1 {
          margin: 6px 0 0;
          font-size: clamp(34px, 4vw, 48px);
          line-height: 1.03;
          letter-spacing: -.045em;
          color: var(--text);
        }

        .profile-handle {
          margin-top: 5px;
          color: var(--muted);
          font-size: 14px;
        }

        .profile-identity p {
          max-width: 700px;
          margin: 18px 0 0;
          color: #c7bddb;
          font-size: 14px;
          line-height: 1.7;
        }

        .profile-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 14px 20px;
          margin-top: 20px;
          color: #8f82aa;
          font-size: 11px;
        }

        .profile-meta span {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .profile-actions {
          display: flex;
          flex-direction: column;
          gap: 9px;
          align-items: stretch;
          min-width: 145px;
        }

        .profile-share {
          height: 36px;
          padding: 0 14px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          border: 1px solid var(--line);
          border-radius: 10px;
          color: var(--muted);
          font-size: 11px;
          background: rgba(255,255,255,.025);
        }

        .profile-content {
          max-width: 1180px;
          margin: 0 auto;
          padding: 28px 32px 70px;
        }

        .profile-stats {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          border: 1px solid var(--line);
          background: rgba(255,255,255,.018);
          border-radius: 14px;
          overflow: hidden;
        }

        .profile-stats > div {
          padding: 20px 22px;
          border-right: 1px solid var(--line);
        }

        .profile-stats > div:last-child {
          border-right: 0;
        }

        .profile-stats span {
          display: block;
          color: var(--muted);
          font-size: 11px;
          margin-bottom: 7px;
        }

        .profile-stats strong {
          display: block;
          color: var(--text);
          font-size: 25px;
          letter-spacing: -.03em;
        }

        .profile-stats small {
          display: block;
          margin-top: 4px;
          color: #756a8f;
          font-size: 10px;
        }

        .profile-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 290px;
          gap: 20px;
          margin-top: 20px;
        }

        .profile-main {
          min-width: 0;
        }

        .profile-sidebar {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .profile-section,
        .about-card,
        .share-card {
          border: 1px solid var(--line);
          background:
            linear-gradient(
              145deg,
              rgba(20,16,32,.82),
              rgba(12,8,22,.74)
            );
          border-radius: 16px;
        }

        .profile-section {
          padding: 22px;
          margin-bottom: 20px;
        }

        .section-heading {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 14px;
          margin-bottom: 18px;
        }

        .section-heading h2 {
          margin: 4px 0 0;
          font-size: 18px;
          letter-spacing: -.02em;
        }

        .section-heading > span,
        .activity-total {
          color: var(--muted);
          font-size: 11px;
        }

        .repo-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0,1fr));
          gap: 12px;
        }

        .repo-card {
          padding: 17px;
          border: 1px solid rgba(168,85,247,.11);
          border-radius: 13px;
          background: rgba(255,255,255,.018);
          transition:
            transform .15s ease,
            border-color .15s ease,
            background .15s ease;
        }

        .repo-card:hover {
          transform: translateY(-2px);
          border-color: rgba(34,211,238,.28);
          background: rgba(255,255,255,.03);
        }

        .repo-card-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .repo-icon {
          width: 32px;
          height: 32px;
          display: grid;
          place-items: center;
          border-radius: 9px;
          color: #22d3ee;
          background: rgba(34,211,238,.08);
          border: 1px solid rgba(34,211,238,.13);
        }

        .repo-arrow {
          color: #6f6585;
        }

        .repo-card h3 {
          margin: 15px 0 6px;
          font-size: 14px;
          color: var(--text);
        }

        .repo-card p {
          min-height: 42px;
          margin: 0;
          color: #8f82a3;
          font-size: 11px;
          line-height: 1.55;
        }

        .repo-card-footer {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          margin-top: 15px;
          padding-top: 12px;
          border-top: 1px solid rgba(255,255,255,.05);
          color: #6f6585;
          font-size: 10px;
        }

        .repo-card-footer span:first-child {
          display: flex;
          align-items: center;
          gap: 5px;
        }

        .repo-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #22d3ee;
        }

        .contribution-shell {
          padding: 16px;
          border: 1px solid rgba(255,255,255,.05);
          border-radius: 12px;
          background: rgba(255,255,255,.015);
          overflow: hidden;
        }

        .contribution-topline {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 14px;
          margin-bottom: 14px;
          color: #756b88;
          font-size: 10px;
        }

        .contribution-legend {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .contribution-legend i {
          width: 10px;
          height: 10px;
          border-radius: 2px;
          border: 1px solid rgba(255,255,255,.04);
        }

        .contribution-grid {
          display: grid;
          grid-template-rows: repeat(7, 9px);
          grid-auto-columns: 9px;
          grid-auto-flow: column;
          gap: 3px;
          width: max-content;
          max-width: 100%;
        }

        .contribution-cell {
          width: 9px;
          height: 9px;
          border-radius: 2px;
          border: 1px solid rgba(255,255,255,.03);
        }

        .footprint-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0,1fr));
          gap: 10px;
        }

        .footprint-item {
          display: flex;
          gap: 12px;
          align-items: center;
          padding: 14px;
          border-radius: 11px;
          border: 1px solid rgba(255,255,255,.05);
          background: rgba(255,255,255,.018);
          color: #22d3ee;
        }

        .footprint-item strong {
          display: block;
          color: var(--text);
          font-size: 16px;
        }

        .footprint-item span {
          display: block;
          margin-top: 2px;
          color: #756b88;
          font-size: 10px;
        }

        .about-card {
          padding: 20px;
        }

        .about-card h2 {
          margin: 5px 0 0;
          font-size: 18px;
        }

        .about-card > p {
          margin: 12px 0 0;
          color: #8f82a3;
          font-size: 12px;
          line-height: 1.65;
        }

        .about-divider {
          height: 1px;
          background: var(--line);
          margin: 18px 0 4px;
        }

        .about-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 10px 0;
          color: #7c728d;
          font-size: 11px;
        }

        .about-row strong {
          color: #dcd2e8;
          font-weight: 600;
          text-align: right;
        }

        .share-card {
          padding: 20px;
        }

        .share-icon {
          width: 34px;
          height: 34px;
          display: grid;
          place-items: center;
          border-radius: 10px;
          color: #22d3ee;
          background: rgba(34,211,238,.08);
          margin-bottom: 12px;
        }

        .share-card strong {
          color: var(--text);
          font-size: 13px;
        }

        .share-card p {
          margin: 8px 0 12px;
          color: #7e738f;
          font-size: 11px;
          line-height: 1.6;
        }

        .share-url {
          padding: 9px 10px;
          border-radius: 8px;
          background: rgba(0,0,0,.2);
          border: 1px solid rgba(255,255,255,.05);
          color: #8e83a2;
          font: 10px "JetBrains Mono", monospace;
          overflow-x: auto;
        }

        .profile-empty {
          padding: 28px 0 8px;
          color: #766b87;
          font-size: 12px;
        }

        @media (max-width: 900px) {
          .profile-hero-inner {
            flex-wrap: wrap;
          }

          .profile-actions {
            flex-direction: row;
            width: 100%;
          }

          .profile-grid {
            grid-template-columns: 1fr;
          }

          .profile-sidebar {
            display: grid;
            grid-template-columns: 1fr 1fr;
          }

          .profile-stats {
            grid-template-columns: repeat(2,1fr);
          }

          .profile-stats > div:nth-child(2) {
            border-right: 0;
          }

          .profile-stats > div:nth-child(-n+2) {
            border-bottom: 1px solid var(--line);
          }

          .repo-grid {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 620px) {
          .profile-hero-inner,
          .profile-content {
            padding-left: 16px;
            padding-right: 16px;
          }

          .profile-hero-inner {
            padding-top: 38px;
          }

          .profile-avatar {
            width: 72px;
            height: 72px;
            border-radius: 18px;
            font-size: 24px;
          }

          .profile-actions {
            flex-direction: column;
          }

          .profile-sidebar {
            display: flex;
          }

          .profile-stats {
            grid-template-columns: 1fr 1fr;
          }

          .footprint-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </>
  );
}