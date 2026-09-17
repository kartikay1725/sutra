"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { Card } from "@/components/ui";
import { repositoryService, type Repository } from "@/lib/repositories";
import { taskService } from "@/lib/tasks";

type NewTaskModalProps = {
  onClose: () => void;
  onSuccess: () => void;
};

export default function NewTaskModal({
  onClose,
  onSuccess,
}: NewTaskModalProps) {
  const [repositories, setRepositories] = useState<
    Repository[]
  >([]);

  const [repositoryId, setRepositoryId] =
    useState("");

  const [title, setTitle] = useState("");
  const [description, setDescription] =
    useState("");


  const [priority, setPriority] =
    useState("medium");

  const [taskType, setTaskType] =
    useState("feature");
    

  const [loading, setLoading] =
    useState(true);

  const [creating, setCreating] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadRepositories = async () => {
      try {
        setLoading(true);
        setError(null);

        const rows =
          await repositoryService.listRepositories();

        if (cancelled) {
          return;
        }

        const ownedRepositories =
          rows.filter(
            (repository) =>
              Boolean(repository.owner),
          );

        setRepositories(
          ownedRepositories,
        );

        if (
          ownedRepositories.length > 0
        ) {
          setRepositoryId(
            ownedRepositories[0].id,
          );
        }
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Failed to load repositories.",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadRepositories();

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedRepository =
    repositories.find(
      (repository) =>
        repository.id === repositoryId,
    ) ?? null;

  const canSubmit =
    Boolean(
      selectedRepository &&
        title.trim() &&
        !creating &&
        !loading,
    );

  const handleCreate = async () => {
    if (!canSubmit || !selectedRepository) {
      return;
    }

    if (!selectedRepository.owner) {
      setError(
        "The selected repository does not expose its owner.",
      );
      return;
    }

    try {
      setCreating(true);
      setError(null);

      await taskService.createTask(
        selectedRepository.owner,
        selectedRepository.name,
        {
          title: title.trim(),
          description:
            description.trim() || "",
          priority,
          task_type: taskType,
        },
      );

      onSuccess();
    } catch (err) {
      console.error(
        "Failed to create task",
        err,
      );

      setError(
        err instanceof Error
          ? err.message
          : "Failed to create task.",
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        background: "rgba(0,0,0,.85)",
        display: "grid",
        placeItems: "center",
        padding: 20,
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
          maxHeight: "85vh",
          overflow: "auto",
        }}
      >
        <div className="card-head">
          <div>
            <div className="h2">
              New Task
            </div>

            <div className="sub">
              Create real engineering work in
              one of your repositories.
            </div>
          </div>

          <button
            type="button"
            className="iconbtn"
            onClick={onClose}
            disabled={creating}
          >
            <X size={15} />
          </button>
        </div>

        <div className="card-pad">
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

          {loading ? (
            <div
              className="sub"
              style={{
                padding: "20px 0",
              }}
            >
              Loading repositories...
            </div>
          ) : repositories.length === 0 ? (
            <>
              <div
                className="sub"
                style={{
                  marginBottom: 18,
                }}
              >
                You do not have any repositories
                available for task creation.
              </div>

              <div className="actions">
                <button
                  type="button"
                  className="btn"
                  onClick={onClose}
                >
                  Close
                </button>
              </div>
            </>
          ) : (
            <>
              <label
                className="field"
                style={{
                  display: "block",
                  marginBottom: 14,
                }}
              >
                <span className="meta">
                  Repository
                </span>

                <select
                  className="input"
                  value={repositoryId}
                  onChange={(event) =>
                    setRepositoryId(
                      event.target.value,
                    )
                  }
                  disabled={creating}
                  style={{
                    width: "100%",
                    marginTop: 6,
                  }}
                >
                  {repositories.map(
                    (repository) => (
                      <option
                        key={repository.id}
                        value={repository.id}
                      >
                        {repository.name}
                      </option>
                    ),
                  )}
                </select>
              </label>

              <label
                className="field"
                style={{
                  display: "block",
                  marginBottom: 14,
                }}
              >
                <span className="meta">
                  Title
                </span>

                <input
                  className="input"
                  value={title}
                  onChange={(event) =>
                    setTitle(
                      event.target.value,
                    )
                  }
                  placeholder="What needs to be built?"
                  maxLength={255}
                  disabled={creating}
                  style={{
                    width: "100%",
                    marginTop: 6,
                  }}
                />
              </label>

              <label
                className="field"
                style={{
                  display: "block",
                  marginBottom: 14,
                }}
              >
                <span className="meta">
                  Description
                </span>

                <textarea
                  className="input"
                  value={description}
                  onChange={(event) =>
                    setDescription(
                      event.target.value,
                    )
                  }
                  placeholder="Describe the expected outcome..."
                  maxLength={10000}
                  rows={5}
                  disabled={creating}
                  style={{
                    width: "100%",
                    marginTop: 6,
                    resize: "vertical",
                  }}
                />
              </label>

              <div
                className="grid g2"
                style={{
                  gap: 14,
                  marginBottom: 18,
                }}
              >
                <label
                  className="field"
                  style={{
                    display: "block",
                  }}
                >
                  <span className="meta">
                    Priority
                  </span>

                  <select
                    className="input"
                    value={priority}
                    onChange={(event) =>
                      setPriority(
                        event.target.value,
                      )
                    }
                    disabled={creating}
                    style={{
                      width: "100%",
                      marginTop: 6,
                    }}
                  >
                    <option value="low">
                      Low
                    </option>
                    <option value="medium">
                      Medium
                    </option>
                    <option value="high">
                      High
                    </option>
                    <option value="critical">
                      Critical
                    </option>
                  </select>
                </label>

                <label
                  className="field"
                  style={{
                    display: "block",
                  }}
                >
                  <span className="meta">
                    Type
                  </span>

                  <select
                    className="input"
                    value={taskType}
                    onChange={(event) =>
                      setTaskType(
                        event.target.value,
                      )
                    }
                    disabled={creating}
                    style={{
                      width: "100%",
                      marginTop: 6,
                    }}
                  >
                    <option value="feature">
                      Feature
                    </option>
                    <option value="bugfix">
                      Bug fix
                    </option>
                    <option value="refactor">
                      Refactor
                    </option>
                    <option value="security">
                      Security
                    </option>
                    <option value="documentation">
                      Documentation
                    </option>
                  </select>
                </label>
              </div>

              <div
                className="actions"
                style={{
                  justifyContent:
                    "flex-end",
                  gap: 10,
                }}
              >
                <button
                  type="button"
                  className="btn"
                  onClick={onClose}
                  disabled={creating}
                >
                  Cancel
                </button>

                <button
                  type="button"
                  className="btn primary"
                  onClick={() =>
                    void handleCreate()
                  }
                  disabled={!canSubmit}
                >
                  {creating
                    ? "Creating..."
                    : "Create task"}
                </button>
              </div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}