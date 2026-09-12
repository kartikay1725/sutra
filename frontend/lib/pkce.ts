/**
 * PKCE (RFC 7636) & OAuth State Generation Utilities.
 * Handles cryptographically random code_verifier, SHA-256 S256 code_challenge,
 * and ephemeral browser test session persistence in sessionStorage (never localStorage).
 */

export interface PkceSession {
  verifier: string;
  challenge: string;
  state: string;
  createdAt: number;
}

export const PKCE_SESSION_STORAGE_KEY = 'sutra_oauth_browser_test_session';

/**
 * Encodes an ArrayBuffer or Uint8Array to base64url format (RFC 7636 Section 3).
 */
export function base64UrlEncode(buffer: ArrayBuffer | Uint8Array): string {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/**
 * Generates a cryptographically random state parameter.
 */
export function createRandomState(prefix: string = 'sutra_test_'): string {
  const cryptoObj = typeof window !== 'undefined' && window.crypto ? window.crypto : globalThis.crypto;
  if (cryptoObj?.getRandomValues) {
    const bytes = new Uint8Array(18);
    cryptoObj.getRandomValues(bytes);
    return `${prefix}${base64UrlEncode(bytes)}`;
  }
  return `${prefix}${Math.random().toString(36).substring(2, 15)}`;
}

/**
 * Computes the S256 code_challenge for a given code_verifier using SHA-256.
 */
export async function deriveCodeChallengeS256(verifier: string): Promise<string> {
  const cryptoObj = typeof window !== 'undefined' && window.crypto ? window.crypto : globalThis.crypto;
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const hashBuffer = await cryptoObj.subtle.digest('SHA-256', data);
  return base64UrlEncode(hashBuffer);
}

/**
 * Generates a fresh, cryptographically random PKCE code_verifier (32 bytes / 43 chars),
 * derives the S256 code_challenge, and generates a fresh random state.
 */
export async function generatePkceSession(): Promise<PkceSession> {
  const cryptoObj = typeof window !== 'undefined' && window.crypto ? window.crypto : globalThis.crypto;
  const verifierBytes = new Uint8Array(32);
  cryptoObj.getRandomValues(verifierBytes);
  const verifier = base64UrlEncode(verifierBytes);
  const challenge = await deriveCodeChallengeS256(verifier);
  const state = createRandomState();
  return {
    verifier,
    challenge,
    state,
    createdAt: Date.now(),
  };
}

/**
 * Ephemerally persists the browser test session strictly in sessionStorage.
 * NEVER writes to localStorage.
 */
export function saveBrowserTestSession(session: PkceSession): void {
  if (typeof window !== 'undefined' && window.sessionStorage) {
    try {
      window.sessionStorage.setItem(PKCE_SESSION_STORAGE_KEY, JSON.stringify(session));
    } catch {
      // Ignore storage errors in restricted contexts
    }
  }
}

/**
 * Retrieves the ephemeral browser test session from sessionStorage.
 */
export function getBrowserTestSession(): PkceSession | null {
  if (typeof window !== 'undefined' && window.sessionStorage) {
    try {
      const raw = window.sessionStorage.getItem(PKCE_SESSION_STORAGE_KEY);
      if (raw) {
        return JSON.parse(raw) as PkceSession;
      }
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Clears the ephemeral browser test session from sessionStorage.
 */
export function clearBrowserTestSession(): void {
  if (typeof window !== 'undefined' && window.sessionStorage) {
    try {
      window.sessionStorage.removeItem(PKCE_SESSION_STORAGE_KEY);
    } catch {
      // Ignore
    }
  }
}
