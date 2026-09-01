"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { apiPublic } from "@/lib/api";

export function StarButton({ owner, repo, initialStarred = false, count = 0 }: { owner: string, repo: string, initialStarred?: boolean, count?: number }) {
  const [starred, setStarred] = useState(initialStarred);
  const [loading, setLoading] = useState(false);

  const toggleStar = async () => {
    setLoading(true);
    try {
      if (starred) {
        await apiPublic(`/v1/social/stars/${owner}/${repo}`, { method: "DELETE" });
      } else {
        await apiPublic(`/v1/social/stars/${owner}/${repo}`, { method: "POST" });
      }
      setStarred(!starred);
    } catch (e) {
      console.error("Failed to toggle star", e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button 
      className={`btn transition-all ${starred ? "starred" : ""}`}
      onClick={toggleStar}
      disabled={loading}
      style={{ display: "flex", alignItems: "center", gap: "6px" }}
    >
      <Star 
        size={16} 
        className={starred ? "yellow" : "dim"} 
        fill={starred ? "var(--color-yellow)" : "none"}
        style={{ transition: "all 0.2s ease" }}
      />
      {starred ? "Starred" : "Star"}
    </button>
  );
}
