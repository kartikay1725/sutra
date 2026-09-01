"use client";

import { useState } from "react";
import { Check, Copy, Share2 } from "lucide-react";

export function ShareProfileButton({
  username,
}: {
  username: string;
}) {
  const [copied, setCopied] =
    useState(false);

  const share = async () => {
    const url =
      `${window.location.origin}/profile/${encodeURIComponent(
        username,
      )}`;

    try {
      if (
        navigator.share
      ) {
        await navigator.share({
          title: `${username} on SUTRA`,
          url,
        });

        return;
      }

      await navigator.clipboard.writeText(
        url,
      );

      setCopied(true);

      window.setTimeout(
        () => setCopied(false),
        1800,
      );
    } catch {
      // User cancelled native share.
    }
  };

  return (
    <button
      type="button"
      onClick={() =>
        void share()
      }
      className="profile-share"
    >
      {copied ? (
        <Check size={14} />
      ) : (
        <Share2 size={14} />
      )}

      {copied
        ? "Copied"
        : "Share profile"}
    </button>
  );
}