"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AppShell,
  PageHead,
  Card,
  Btn,
} from "@/components/shell";
import { authService } from "@/lib/auth";
import { apiAuth } from "@/lib/api";
import {
  Github,
  Linkedin,
  Twitter,
  Instagram,
  Youtube,
  Globe,
  MessageCircle,
  Save,
  ExternalLink,
} from "lucide-react";
import { profileService, type ContributionGraph } from "@/lib/profiles";

type SocialLinks = {
  github: string;
  linkedin: string;
  x: string;
  instagram: string;
  reddit: string;
  youtube: string;
  website: string;
};

const emptyLinks: SocialLinks = {
  github: "",
  linkedin: "",
  x: "",
  instagram: "",
  reddit: "",
  youtube: "",
  website: "",
};

const socialFields = [
  {
    key: "github" as const,
    label: "GitHub",
    placeholder: "https://github.com/username",
    icon: Github,
  },
  {
    key: "linkedin" as const,
    label: "LinkedIn",
    placeholder: "https://linkedin.com/in/username",
    icon: Linkedin,
  },
  {
    key: "x" as const,
    label: "X",
    placeholder: "https://x.com/username",
    icon: Twitter,
  },
  {
    key: "instagram" as const,
    label: "Instagram",
    placeholder: "https://instagram.com/username",
    icon: Instagram,
  },
  {
    key: "reddit" as const,
    label: "Reddit",
    placeholder: "https://reddit.com/u/username",
    icon: MessageCircle,
  },
  {
    key: "youtube" as const,
    label: "YouTube",
    placeholder: "https://youtube.com/@username",
    icon: Youtube,
  },
  {
    key: "website" as const,
    label: "Website",
    placeholder: "https://example.com",
    icon: Globe,
  },
];

export default function ProfilePage() {
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [bio, setBio] = useState("");
  const [socialLinks, setSocialLinks] =
    useState<SocialLinks>(emptyLinks);
  const [contributions, setContributions] =
    useState<ContributionGraph | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const user = await authService.getCurrentUser();

        setUsername(user.username || "");
        setEmail(user.email || "");
        setFullName(user.full_name || "");
        setBio(user.bio || "");
        setSocialLinks({
          ...emptyLinks,
          ...((user as any).social_links || {}),
        });

        if (user.username) {
          try {
            const graph = await profileService.getContributions(user.username);
            setContributions(graph);
          } catch (e) {
            console.warn("Could not load contribution graph:", e);
          }
        }
      } catch (err: any) {
        console.error(err);
        router.replace("/login");
        return;
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [router]);

  const updateSocial = (
    key: keyof SocialLinks,
    value: string,
  ) => {
    setSocialLinks((current) => ({
      ...current,
      [key]: value,
    }));
    setSaved(false);
  };

  const saveProfile = async () => {
    setSaving(true);
    setSaved(false);
    setError("");

    try {
      await apiAuth("/v1/auth/me", {
        method: "PATCH",
        body: JSON.stringify({
          full_name: fullName,
          email,
          bio,
          social_links: socialLinks,
        }),
      });

      setSaved(true);
    } catch (err: any) {
      console.error(err);
      setError(
        err?.detail ||
          err?.message ||
          "Failed to save profile.",
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div
          style={{
            padding: 40,
            color: "var(--muted)",
          }}
        >
          Loading profile…
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div
        style={{
          maxWidth: 900,
          margin: "0 auto",
          padding: "28px 32px 60px",
        }}
      >
        <PageHead
          eyebrow="Your account"
          title="Profile"
          sub="Edit the identity people see on your public SUTRA portfolio."
        />

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 18,
          }}
        >
          <Card>
            <div
              className="card-pad"
              style={{
                padding: 24,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 16,
                  marginBottom: 24,
                }}
              >
                <div
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 18,
                    display: "grid",
                    placeItems: "center",
                    background:
                      "linear-gradient(135deg,#a855f7,#22d3ee)",
                    color: "#fff",
                    fontSize: 22,
                    fontWeight: 700,
                  }}
                >
                  {(fullName || username || "?")
                    .charAt(0)
                    .toUpperCase()}
                </div>

                <div>
                  <div
                    style={{
                      fontSize: 17,
                      fontWeight: 700,
                    }}
                  >
                    {fullName || username}
                  </div>

                  <div
                    style={{
                      color: "var(--muted)",
                      fontSize: 12,
                      marginTop: 3,
                    }}
                  >
                    @{username}
                  </div>
                </div>
              </div>

              <div className="field">
                <label className="label">
                  Username
                </label>

                <input
                  className="input"
                  value={username}
                  disabled
                />
              </div>

              <div className="field">
                <label className="label">
                  Email
                </label>

                <input
                  className="input"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setSaved(false);
                  }}
                />
              </div>

              <div className="field">
                <label className="label">
                  Display name
                </label>

                <input
                  className="input"
                  placeholder="Your name"
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value);
                    setSaved(false);
                  }}
                />
              </div>

              <div className="field">
                <label className="label">
                  Bio
                </label>

                <textarea
                  className="input"
                  placeholder="Tell people what you build, what you care about, or what you're working on."
                  value={bio}
                  onChange={(e) => {
                    setBio(e.target.value);
                    setSaved(false);
                  }}
                  style={{
                    minHeight: 120,
                    padding: "11px 12px",
                    resize: "vertical",
                  }}
                />
              </div>
            </div>
          </Card>

          <Card>
            <div className="card-pad" style={{ padding: 24 }}>
              <div
                style={{
                  marginBottom: 20,
                }}
              >
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 700,
                  }}
                >
                  Social links
                </div>

                <div
                  className="sub"
                  style={{
                    marginTop: 5,
                  }}
                >
                  Add the places where people can
                  find or contact you. Empty links
                  stay hidden from your public profile.
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                }}
              >
                {socialFields.map(
                  ({
                    key,
                    label,
                    placeholder,
                    icon: Icon,
                  }) => (
                    <div
                      key={key}
                      style={{
                        display: "grid",
                        gridTemplateColumns:
                          "150px minmax(0,1fr)",
                        gap: 12,
                        alignItems: "center",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 9,
                          fontSize: 12,
                          color: "var(--fg)",
                        }}
                      >
                        <Icon
                          size={15}
                          className="muted"
                        />
                        {label}
                      </div>

                      <input
                        className="input"
                        value={socialLinks[key]}
                        placeholder={placeholder}
                        onChange={(e) =>
                          updateSocial(
                            key,
                            e.target.value,
                          )
                        }
                      />
                    </div>
                  ),
                )}
              </div>
            </div>
          </Card>

          {/* GitHub Contribution Activity Card */}
          <Card>
            <div className="card-pad" style={{ padding: 24 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 16,
                  flexWrap: "wrap",
                  gap: 10,
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: 16,
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <Github size={16} color="var(--cyan)" />
                    GitHub Contribution Activity
                  </div>
                  <div className="sub" style={{ marginTop: 4 }}>
                    Your public profile engineering calendar reflects activity synchronized with GitHub.
                  </div>
                </div>

                {contributions?.github_synced ? (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#22d3ee",
                      background: "rgba(34, 211, 238, 0.12)",
                      border: "1px solid rgba(34, 211, 238, 0.25)",
                      padding: "3px 10px",
                      borderRadius: 6,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                    }}
                  >
                    <Github size={12} />
                    Synced with @{contributions.github_account}
                  </span>
                ) : (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: "var(--muted)",
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid var(--line)",
                      padding: "3px 10px",
                      borderRadius: 6,
                    }}
                  >
                    Add your GitHub profile link above to synchronize
                  </span>
                )}
              </div>

              {contributions && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    background: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid var(--line)",
                    borderRadius: 8,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                    <span style={{ fontSize: 22, fontWeight: 700, color: "var(--fg)" }}>
                      {contributions.total_contributions}
                    </span>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>
                      recorded contributions across the last 365 days
                    </span>
                  </div>

                  <Btn
                    sm
                    onClick={() =>
                      router.push(
                        `/profile/${encodeURIComponent(username)}`,
                      )
                    }
                  >
                    <ExternalLink size={12} />
                    View calendar
                  </Btn>
                </div>
              )}
            </div>
          </Card>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
            }}
          >
            <div>
              {error && (
                <div
                  style={{
                    color: "var(--red)",
                    fontSize: 12,
                  }}
                >
                  {error}
                </div>
              )}

              {saved && !error && (
                <div
                  style={{
                    color: "var(--green)",
                    fontSize: 12,
                  }}
                >
                  Profile saved.
                </div>
              )}
            </div>

            <div
              style={{
                display: "flex",
                gap: 9,
              }}
            >
              <Btn
                onClick={() =>
                  router.push(
                    `/profile/${encodeURIComponent(
                      username,
                    )}`,
                  )
                }
              >
                <ExternalLink size={14} />
                View public profile
              </Btn>

              <Btn
                primary
                onClick={() =>
                  void saveProfile()
                }
                disabled={saving}
              >
                <Save size={14} />
                {saving
                  ? "Saving..."
                  : "Save profile"}
              </Btn>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}