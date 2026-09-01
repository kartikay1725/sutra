"use client";

import {
  FormEvent,
  useState,
} from "react";
import { X, Plus } from "lucide-react";
import { useRouter } from "next/navigation";

import { Card } from "@/components/ui";
import { repositoryService } from "@/lib/repositories";

type NewRepositoryModalProps = {
  onClose: () => void;
};

export default function NewRepositoryModal({
  onClose,
}: NewRepositoryModalProps) {
  const router = useRouter();

  const [name, setName] = useState("");
  const [description, setDescription] =
    useState("");

  const [visibility, setVisibility] =
    useState<"public" | "private">("private");

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    const trimmedName = name.trim();
    const trimmedDescription =
      description.trim();

    if (!trimmedName) {
      setError(
        "Repository name is required.",
      );
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const repository =
        await repositoryService.createRepository(
          trimmedName,
          trimmedDescription,
          visibility === "private",
        );

      /*
       * The repository has now been created by
       * the real backend. Go directly to it.
       */
      router.push(
        `/repositories/${repository.name}`,
      );

      router.refresh();
    } catch (err) {
      console.error(
        "Failed to create repository",
        err,
      );

      setError(
        err instanceof Error
          ? err.message
          : "Failed to create repository.",
      );

      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-repository-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        display: "grid",
        placeItems: "center",
        padding: 20,
        background: "rgba(0, 0, 0, 0.68)",
        backdropFilter: "blur(10px)",
      }}
      onMouseDown={(event) => {
        if (
          event.target ===
          event.currentTarget
        ) {
          onClose();
        }
      }}
    >
      <Card
        style={{
          width: "min(100%, 620px)",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
      >
        <div className="card-head">
          <div>
            <div
              className="h2"
              id="new-repository-title"
            >
              New Repository
            </div>

            <div className="sub">
              Create a real Git repository in
              your SUTRA workspace.
            </div>
          </div>

          <button
            type="button"
            className="iconbtn"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close"
          >
            <X size={15} />
          </button>
        </div>

        <form
          className="card-pad"
          onSubmit={handleSubmit}
        >
          {error && (
            <div
              className="sub"
              style={{
                color: "#ff8fa0",
                marginBottom: 16,
              }}
            >
              {error}
            </div>
          )}

          <label
            style={{
              display: "block",
              marginBottom: 18,
            }}
          >
            <div className="meta">
              Repository name
            </div>

            <input
              className="input"
              value={name}
              onChange={(event) =>
                setName(event.target.value)
              }
              placeholder="my-project"
              maxLength={100}
              autoFocus
              disabled={submitting}
              style={{
                width: "100%",
                marginTop: 7,
              }}
            />
          </label>

          <label
            style={{
              display: "block",
              marginBottom: 18,
            }}
          >
            <div className="meta">
              Description
            </div>

            <textarea
              className="input"
              value={description}
              onChange={(event) =>
                setDescription(
                  event.target.value,
                )
              }
              placeholder="What is this repository for?"
              rows={4}
              maxLength={1000}
              disabled={submitting}
              style={{
                width: "100%",
                marginTop: 7,
                resize: "vertical",
              }}
            />
          </label>

          <div
            style={{
              marginBottom: 22,
            }}
          >
            <div
              className="meta"
              style={{
                marginBottom: 9,
              }}
            >
              Visibility
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "1fr 1fr",
                gap: 10,
              }}
            >
              <button
                type="button"
                className={
                  visibility === "private"
                    ? "btn primary"
                    : "btn"
                }
                onClick={() =>
                  setVisibility("private")
                }
                disabled={submitting}
              >
                Private
              </button>

              <button
                type="button"
                className={
                  visibility === "public"
                    ? "btn primary"
                    : "btn"
                }
                onClick={() =>
                  setVisibility("public")
                }
                disabled={submitting}
              >
                Public
              </button>
            </div>

            <div
              className="meta"
              style={{
                marginTop: 8,
              }}
            >
              {visibility === "private"
                ? "Only authorized users and agents can access it."
                : "The repository is publicly discoverable."}
            </div>
          </div>

          <div
            className="actions"
            style={{
              justifyContent: "flex-end",
              gap: 10,
            }}
          >
            <button
              type="button"
              className="btn"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="btn primary"
              disabled={
                submitting ||
                !name.trim()
              }
            >
              <Plus size={14} />

              {submitting
                ? "Creating..."
                : "Create repository"}
            </button>
          </div>
        </form>
      </Card>
    </div>
  );
}