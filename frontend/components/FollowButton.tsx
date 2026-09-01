"use client";

import { useState } from "react";
import { UserPlus, UserMinus } from "lucide-react";
import { apiAuth } from "@/lib/api";

export function FollowButton({
  username,
  initialFollowing = false,
}: {
  username: string;
  initialFollowing?: boolean;
}) {
  const [following, setFollowing] =
    useState(initialFollowing);

  const [loading, setLoading] =
    useState(false);

  const toggleFollow = async () => {
    if (loading) return;

    const previous = following;

    setFollowing(!previous);
    setLoading(true);

    try {
      await apiAuth(
        `/v1/users/${encodeURIComponent(
          username,
        )}/follow`,
        {
          method: previous
            ? "DELETE"
            : "POST",
        },
      );
    } catch (error) {
      console.error(
        "Failed to toggle follow",
        error,
      );

      setFollowing(previous);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      className={`btn ${
        following ? "muted" : "primary"
      }`}
      onClick={toggleFollow}
      disabled={loading}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
      }}
    >
      {following ? (
        <>
          <UserMinus size={16} />
          Following
        </>
      ) : (
        <>
          <UserPlus size={16} />
          Follow
        </>
      )}
    </button>
  );
}