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

import type { Metadata } from "next";

// Always SSR — contribution data is real-time and user-specific.
// Without this Next.js may statically cache the first render.
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{
    username: string;
  }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { username } = await params;
  try {
    const profile = await profileService.getProfile(username);
    const title = profile?.full_name
      ? `${profile.full_name} (@${profile.username}) — SUTRA`
      : `@${username} — SUTRA`;
    const description =
      profile?.bio ||
      `Public engineering profile for @${username} on SUTRA — AI-Native Engineering Control Plane.`;
    const canonical = `https://sutra.sudarshanai.com/profile/${encodeURIComponent(username)}`;

    return {
      title,
      description,
      alternates: { canonical },
      openGraph: {
        title,
        description,
        url: canonical,
        siteName: "SUTRA",
        type: "profile",
        images: [
          {
            url: "https://sutra.sudarshanai.com/og-image.png",
            width: 1200,
            height: 630,
            alt: `${title} on SUTRA`,
          },
        ],
      },
      twitter: {
        card: "summary_large_image",
        title,
        description,
        images: ["https://sutra.sudarshanai.com/og-image.png"],
      },
    };
  } catch {
    return {
      title: `@${username} — SUTRA`,
      description: `Public engineering profile for @${username} on SUTRA — AI-Native Engineering Control Plane.`,
    };
  }
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
    return "#181818";
  }

  // Clamp and normalize on a log scale (same approach GitHub uses)
  const effectiveMax = Math.max(maxCount, count, 10);
  const ratio = Math.log1p(count) / Math.log1p(effectiveMax);

  if (ratio < 0.25) return "rgba(34, 197, 94, 0.25)";
  if (ratio < 0.50) return "rgba(34, 197, 94, 0.50)";
  if (ratio < 0.75) return "rgba(34, 197, 94, 0.75)";
  return "#22c55e";
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
                            "1px solid #242424",
                          background:
                            "#151515",
                          color: "#C4C4C4",
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
                            color: "#3B82F6",
                            background: "rgba(59, 130, 246, 0.1)",
                            border: "1px solid rgba(59, 130, 246, 0.25)",
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
                            "#181818",
                        }}
                      />
                      <i
                        style={{
                          background:
                            "rgba(34, 197, 94, 0.25)",
                        }}
                      />
                      <i
                        style={{
                          background:
                            "rgba(34, 197, 94, 0.50)",
                        }}
                      />
                      <i
                        style={{
                          background:
                            "rgba(34, 197, 94, 0.75)",
                        }}
                      />
                      <i
                        style={{
                          background:
                            "#22c55e",
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
                    <Code2 size={18} />
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
                  <Copy size={17} />
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
          background: #0B0B0B;
          color: #F5F5F5;
        }

        .profile-hero {
          border-bottom: 1px solid #242424;
          background: #111111;
        }

        .profile-hero-inner {
          max-width: 1180px;
          margin: 0 auto;
          padding: 50px 32px 40px;
          display: flex;
          align-items: flex-start;
          gap: 24px;
        }

        .profile-avatar {
          width: 88px;
          height: 88px;
          border-radius: 18px;
          flex: 0 0 auto;
          display: grid;
          place-items: center;
          font-size: 28px;
          font-weight: 700;
          color: #F97316;
          background: #181818;
          border: 1px solid #2A2A2A;
          box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        }

        .profile-identity {
          flex: 1;
          min-width: 0;
        }

        .profile-kicker,
        .section-eyebrow {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: .14em;
          color: #F97316;
        }

        .profile-identity h1 {
          margin: 6px 0 0;
          font-size: clamp(30px, 4vw, 42px);
          line-height: 1.05;
          letter-spacing: -.035em;
          color: #F5F5F5;
          font-weight: 700;
        }

        .profile-handle {
          margin-top: 5px;
          color: #8A8A8A;
          font-size: 14px;
        }

        .profile-identity p {
          max-width: 700px;
          margin: 16px 0 0;
          color: #C4C4C4;
          font-size: 14px;
          line-height: 1.65;
        }

        .profile-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 14px 20px;
          margin-top: 18px;
          color: #8A8A8A;
          font-size: 12px;
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
          border: 1px solid #242424;
          border-radius: 8px;
          color: #C4C4C4;
          font-size: 12px;
          background: #151515;
          cursor: pointer;
          transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
        }

        .profile-share:hover {
          border-color: #3A3A3A;
          background: #1D1D1D;
          color: #F5F5F5;
        }

        .profile-content {
          max-width: 1180px;
          margin: 0 auto;
          padding: 28px 32px 70px;
        }

        .profile-stats {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          border: 1px solid #242424;
          background: #151515;
          border-radius: 12px;
          overflow: hidden;
        }

        .profile-stats > div {
          padding: 18px 20px;
          border-right: 1px solid #242424;
        }

        .profile-stats > div:last-child {
          border-right: 0;
        }

        .profile-stats span {
          display: block;
          color: #8A8A8A;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 7px;
        }

        .profile-stats strong {
          display: block;
          color: #F5F5F5;
          font-size: 24px;
          font-weight: 700;
          letter-spacing: -.03em;
        }

        .profile-stats small {
          display: block;
          margin-top: 4px;
          color: #666666;
          font-size: 11px;
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
          border: 1px solid #242424;
          background: #151515;
          border-radius: 12px;
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
          color: #F5F5F5;
          letter-spacing: -.02em;
        }

        .section-heading > span,
        .activity-total {
          color: #8A8A8A;
          font-size: 11px;
        }

        .repo-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0,1fr));
          gap: 12px;
        }

        .repo-card {
          padding: 18px;
          border: 1px solid #242424;
          border-radius: 10px;
          background: #181818;
          text-decoration: none;
          display: block;
          transition: border-color .15s ease, background .15s ease;
        }

        .repo-card:hover {
          border-color: #3A3A3A;
          background: #1D1D1D;
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
          border-radius: 8px;
          color: #F97316;
          background: rgba(249, 115, 22, 0.1);
          border: 1px solid rgba(249, 115, 22, 0.2);
        }

        .repo-arrow {
          color: #666666;
          transition: color .15s ease;
        }

        .repo-card:hover .repo-arrow {
          color: #3B82F6;
        }

        .repo-card h3 {
          margin: 14px 0 6px;
          font-size: 14px;
          font-weight: 600;
          color: #F5F5F5;
        }

        .repo-card p {
          min-height: 40px;
          margin: 0;
          color: #8A8A8A;
          font-size: 12px;
          line-height: 1.5;
        }

        .repo-card-footer {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          margin-top: 14px;
          padding-top: 12px;
          border-top: 1px solid #242424;
          color: #666666;
          font-size: 11px;
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
          background: #3B82F6;
        }

        .contribution-shell {
          padding: 16px;
          border: 1px solid #242424;
          border-radius: 10px;
          background: #111111;
          overflow: hidden;
        }

        .contribution-topline {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 14px;
          margin-bottom: 14px;
          color: #8A8A8A;
          font-size: 11px;
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
          border: 1px solid rgba(0,0,0,0.3);
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
          border: 1px solid rgba(0, 0, 0, 0.25);
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
          border-radius: 10px;
          border: 1px solid #242424;
          background: #181818;
          color: #F97316;
        }

        .footprint-item strong {
          display: block;
          color: #F5F5F5;
          font-size: 16px;
          font-weight: 600;
        }

        .footprint-item span {
          display: block;
          margin-top: 2px;
          color: #8A8A8A;
          font-size: 11px;
        }

        .about-card {
          padding: 20px;
        }

        .about-card h2 {
          margin: 5px 0 0;
          font-size: 18px;
          color: #F5F5F5;
        }

        .about-card > p {
          margin: 12px 0 0;
          color: #C4C4C4;
          font-size: 12px;
          line-height: 1.65;
        }

        .about-divider {
          height: 1px;
          background: #242424;
          margin: 18px 0 4px;
        }

        .about-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 10px 0;
          color: #8A8A8A;
          font-size: 12px;
          border-bottom: 1px solid #1D1D1D;
        }

        .about-row strong {
          color: #F5F5F5;
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
          border-radius: 8px;
          color: #F97316;
          background: rgba(249, 115, 22, 0.1);
          border: 1px solid rgba(249, 115, 22, 0.2);
          margin-bottom: 12px;
        }

        .share-card strong {
          color: #F5F5F5;
          font-size: 13px;
        }

        .share-card p {
          margin: 8px 0 12px;
          color: #8A8A8A;
          font-size: 12px;
          line-height: 1.6;
        }

        .share-url {
          padding: 8px 10px;
          border-radius: 6px;
          background: #070707;
          border: 1px solid #242424;
          color: #3B82F6;
          font: 11px "JetBrains Mono", monospace;
          overflow-x: auto;
        }

        .profile-empty {
          padding: 28px 0 8px;
          color: #8A8A8A;
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
            border-bottom: 1px solid #242424;
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
            border-radius: 16px;
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