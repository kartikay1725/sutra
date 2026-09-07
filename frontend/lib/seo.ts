import type { Metadata } from "next";

/**
 * Shared noindex metadata configuration for internal, authenticated,
 * or auth-state application routes.
 */
export const noIndexMetadata: Metadata = {
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: {
      index: false,
      follow: false,
      noimageindex: true,
      "max-video-preview": -1,
      "max-image-preview": "none",
      "max-snippet": -1,
    },
  },
};
