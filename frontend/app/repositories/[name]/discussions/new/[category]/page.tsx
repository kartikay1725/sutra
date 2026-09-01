"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";

import {
  AppShell,
  PageHead,
  Card,
  Btn,
  Badge,
} from "@/components/shell";

import {
  discussionService,
} from "@/lib/discussions";

import {
  authService,
} from "@/lib/auth";

import * as I from "lucide-react";

const CATEGORY_INFO: Record<
  string,
  {
    name: string;
    desc: string;
    icon: React.ReactNode;
  }
> = {
  announcements: {
    name: "Announcements",
    desc: "Updates from maintainers",
    icon: <I.Megaphone size={16} />,
  },
  general: {
    name: "General",
    desc: "Chat about anything and everything here",
    icon: <I.MessageCircle size={16} />,
  },
  ideas: {
    name: "Ideas",
    desc: "Share ideas for new features",
    icon: <I.Lightbulb size={16} />,
  },
  polls: {
    name: "Polls",
    desc: "Take a vote from the community",
    icon: <I.BarChart2 size={16} />,
  },
  "q&a": {
    name: "Q&A",
    desc: "Ask the community for help",
    icon: <I.HelpCircle size={16} />,
  },
  "show and tell": {
    name: "Show and tell",
    desc: "Show off something you've made",
    icon: <I.Eye size={16} />,
  },
};

export default function NewDiscussionFormPage({
  params,
}: {
  params: Promise<{
    name: string;
    category: string;
  }>;
}) {
  const {
    name: repoName,
    category: urlCategory,
  } = use(params);

  const router = useRouter();

  const categoryKey =
    decodeURIComponent(urlCategory)
      .trim()
      .toLowerCase();

  const category =
    CATEGORY_INFO[categoryKey] || {
      name: decodeURIComponent(
        urlCategory,
      ),
      desc: "",
      icon: (
        <I.MessageSquare
          size={16}
        />
      ),
    };

  const [title, setTitle] =
    useState("");

  const [body, setBody] =
    useState("");

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const handleSubmit = async () => {
    const cleanTitle =
      title.trim();

    const cleanBody =
      body.trim();

    if (!cleanTitle) {
      setError(
        "Add a title before creating the discussion.",
      );
      return;
    }

    if (!cleanBody) {
      setError(
        "Add a body before creating the discussion.",
      );
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const user =
        await authService.getCurrentUser();

      const discussion =
        await discussionService.createDiscussion(
          user.username,
          repoName,
          {
            title: cleanTitle,
            body: cleanBody,
            category: category.name,
          },
        );

      router.push(
        `/repositories/${encodeURIComponent(
          repoName,
        )}/discussions/${encodeURIComponent(
          discussion.id,
        )}`,
      );
    } catch (err: any) {
      console.error(
        "Failed to create discussion:",
        err,
      );

      setError(
        err?.detail ||
          err?.message ||
          "Failed to create discussion.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <PageHead
        eyebrow={`Discussions / ${repoName}`}
        title="Start a new discussion"
        sub="Create a real discussion for this repository."
      />

      <div
        style={{
          maxWidth: 860,
          margin: "0 auto",
          padding:
            "0 20px 40px",
        }}
      >
        <Card>
          <div className="card-pad">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 6,
              }}
            >
              <span
                style={{
                  color:
                    "var(--cyan)",
                }}
              >
                {category.icon}
              </span>

              <Badge>
                {category.name}
              </Badge>
            </div>

            <div
              className="sub"
              style={{
                marginBottom: 24,
              }}
            >
              {category.desc}
            </div>

            <div
              style={{
                display: "flex",
                flexDirection:
                  "column",
                gap: 20,
              }}
            >
              <div>
                <label
                  style={{
                    display:
                      "block",
                    fontSize: 13,
                    fontWeight: 600,
                    color:
                      "var(--fg)",
                    marginBottom: 8,
                  }}
                >
                  Title
                </label>

                <input
                  type="text"
                  className="input"
                  value={title}
                  onChange={(event) =>
                    setTitle(
                      event.target.value,
                    )
                  }
                  placeholder="What do you want to discuss?"
                  maxLength={255}
                />
              </div>

              <div>
                <label
                  style={{
                    display:
                      "block",
                    fontSize: 13,
                    fontWeight: 600,
                    color:
                      "var(--fg)",
                    marginBottom: 8,
                  }}
                >
                  Body
                </label>

                <textarea
                  className="input"
                  value={body}
                  onChange={(event) =>
                    setBody(
                      event.target.value,
                    )
                  }
                  placeholder="Share the question, idea, announcement, or context..."
                  style={{
                    minHeight: 220,
                    resize:
                      "vertical",
                    lineHeight: 1.6,
                  }}
                  maxLength={10000}
                />
              </div>

              {error && (
                <div
                  style={{
                    display:
                      "flex",
                    alignItems:
                      "flex-start",
                    gap: 8,
                    padding:
                      "12px 14px",
                    borderRadius: 8,
                    background:
                      "rgba(239,68,68,.08)",
                    border:
                      "1px solid rgba(239,68,68,.25)",
                    color:
                      "var(--red)",
                    fontSize: 13,
                  }}
                >
                  <I.AlertCircle
                    size={15}
                    style={{
                      flexShrink: 0,
                      marginTop: 1,
                    }}
                  />

                  <span>{error}</span>
                </div>
              )}

              <div
                style={{
                  display:
                    "flex",
                  justifyContent:
                    "space-between",
                  alignItems:
                    "center",
                  gap: 12,
                }}
              >
                <Btn
                  type="button"
                  onClick={() =>
                    router.push(
                      `/repositories/${encodeURIComponent(
                        repoName,
                      )}/discussions/new`,
                    )
                  }
                  disabled={
                    submitting
                  }
                >
                  Change category
                </Btn>

                <div
                  className="actions"
                >
                  <Btn
                    type="button"
                    onClick={() =>
                      router.back()
                    }
                    disabled={
                      submitting
                    }
                  >
                    Cancel
                  </Btn>

                  <Btn
                    primary
                    type="button"
                    onClick={
                      handleSubmit
                    }
                    disabled={
                      submitting ||
                      !title.trim() ||
                      !body.trim()
                    }
                  >
                    {submitting
                      ? "Creating..."
                      : "Start discussion"}
                  </Btn>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}