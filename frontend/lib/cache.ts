/**
 * SUTRA Client Caching Engine
 * 
 * Provides:
 * 1. In-memory Map cache for 0ms navigation.
 * 2. In-flight Promise deduplication (coalesces identical concurrent fetches).
 * 3. SessionStorage persistence (survives tab reloads, wiped on tab close).
 * 4. Stale-While-Revalidate (SWR) semantics with change subscription.
 * 5. Explicit lastSyncedAt tracking and manual refresh bypass.
 * 6. Graceful fallback when sessionStorage is unavailable.
 * 
 * STRICT CONSTRAINT: Never stores credentials, tokens, or private secrets.
 */

export interface CacheEntry<T> {
  data: T;
  cachedAt: number; // epoch ms
  staleAt: number;  // epoch ms
  expiresAt: number; // epoch ms
}

export interface CachedFetchOptions {
  /** Fresh window in milliseconds. Data within this window is fresh. Default 30s. */
  staleMs?: number;
  /** Hard expiration in milliseconds. Data older than this is dropped. Default 5m. */
  ttlMs?: number;
  /** If true, bypasses cache and forces a network fetch. */
  forceRefresh?: boolean;
  /** If true, persists the cached item in sessionStorage. Default false. */
  persistSession?: boolean;
  /** If true, persists the cached item in localStorage. Default false. */
  persistLocal?: boolean;
}

export interface CacheMetadata {
  isCached: boolean;
  isStale: boolean;
  lastSyncedAt: number | null;
}

type Listener<T> = (data: T, meta: CacheMetadata) => void;

class ClientCacheManager {
  private memoryCache = new Map<string, CacheEntry<any>>();
  private inFlightRequests = new Map<string, Promise<any>>();
  private listeners = new Map<string, Set<Listener<any>>>();
  private readonly SESSION_PREFIX = "sutra_cache:";
  private readonly LOCAL_PREFIX = "sutra_local_cache:";

  constructor() {
    this.hydrateFromLocal();
    this.hydrateFromSession();
  }

  /**
   * Safely read localStorage on initialization.
   */
  private hydrateFromLocal(): void {
    if (typeof window === "undefined") return;

    try {
      const now = Date.now();
      for (let i = 0; i < window.localStorage.length; i++) {
        const key = window.localStorage.key(i);
        if (key && key.startsWith(this.LOCAL_PREFIX)) {
          const raw = window.localStorage.getItem(key);
          if (raw) {
            try {
              const entry: CacheEntry<any> = JSON.parse(raw);
              if (entry && typeof entry.expiresAt === "number") {
                if (entry.expiresAt > now) {
                  const cacheKey = key.slice(this.LOCAL_PREFIX.length);
                  this.memoryCache.set(cacheKey, entry);
                } else {
                  window.localStorage.removeItem(key);
                }
              }
            } catch {
              window.localStorage.removeItem(key);
            }
          }
        }
      }
    } catch {
      // Local storage might be disabled or restricted in private mode
    }
  }

  /**
   * Safely read sessionStorage on initialization.
   */
  private hydrateFromSession(): void {
    if (typeof window === "undefined") return;

    try {
      const now = Date.now();
      for (let i = 0; i < window.sessionStorage.length; i++) {
        const key = window.sessionStorage.key(i);
        if (key && key.startsWith(this.SESSION_PREFIX)) {
          const raw = window.sessionStorage.getItem(key);
          if (raw) {
            try {
              const entry: CacheEntry<any> = JSON.parse(raw);
              if (entry && typeof entry.expiresAt === "number") {
                if (entry.expiresAt > now) {
                  const cacheKey = key.slice(this.SESSION_PREFIX.length);
                  this.memoryCache.set(cacheKey, entry);
                } else {
                  window.sessionStorage.removeItem(key);
                }
              }
            } catch {
              window.sessionStorage.removeItem(key);
            }
          }
        }
      }
    } catch {
      // Session storage might be disabled or restricted in private mode
    }
  }

  /**
   * Write an entry to memory and optionally to sessionStorage or localStorage.
   */
  public set<T>(
    key: string,
    data: T,
    options: { staleMs?: number; ttlMs?: number; persistSession?: boolean; persistLocal?: boolean } = {}
  ): CacheEntry<T> {
    const now = Date.now();
    const staleMs = options.staleMs ?? 30_000;
    const ttlMs = options.ttlMs ?? 300_000;

    const entry: CacheEntry<T> = {
      data,
      cachedAt: now,
      staleAt: now + staleMs,
      expiresAt: now + ttlMs,
    };

    this.memoryCache.set(key, entry);

    if (options.persistSession && typeof window !== "undefined") {
      try {
        window.sessionStorage.setItem(
          `${this.SESSION_PREFIX}${key}`,
          JSON.stringify(entry)
        );
      } catch {
        // Handle QuotaExceededError or sessionStorage disabled gracefully
      }
    }

    if (options.persistLocal && typeof window !== "undefined") {
      try {
        window.localStorage.setItem(
          `${this.LOCAL_PREFIX}${key}`,
          JSON.stringify(entry)
        );
      } catch {
        // Handle QuotaExceededError or localStorage disabled gracefully
      }
    }

    this.notifyListeners(key, data, {
      isCached: true,
      isStale: false,
      lastSyncedAt: now,
    });

    return entry;
  }

  /**
   * Retrieve an entry from memory cache.
   */
  public get<T>(key: string): CacheEntry<T> | null {
    const entry = this.memoryCache.get(key);
    if (!entry) return null;

    const now = Date.now();
    if (now > entry.expiresAt) {
      this.delete(key);
      return null;
    }

    return entry as CacheEntry<T>;
  }

  /**
   * Invalidate a single key or pattern prefix.
   */
  public delete(key: string): void {
    this.memoryCache.delete(key);
    this.inFlightRequests.delete(key);

    if (typeof window !== "undefined") {
      try {
        window.sessionStorage.removeItem(`${this.SESSION_PREFIX}${key}`);
      } catch {}
      try {
        window.localStorage.removeItem(`${this.LOCAL_PREFIX}${key}`);
      } catch {}
    }
  }

  /**
   * Invalidate all keys matching a prefix.
   */
  public invalidatePrefix(prefix: string): void {
    for (const key of Array.from(this.memoryCache.keys())) {
      if (key.startsWith(prefix)) {
        this.delete(key);
      }
    }
    if (typeof window !== "undefined") {
      try {
        const fullPrefix = `${this.SESSION_PREFIX}${prefix}`;
        const toRemoveSession: string[] = [];
        for (let i = 0; i < window.sessionStorage.length; i++) {
          const k = window.sessionStorage.key(i);
          if (k && k.startsWith(fullPrefix)) {
            toRemoveSession.push(k);
          }
        }
        for (const k of toRemoveSession) {
          window.sessionStorage.removeItem(k);
        }
      } catch {}

      try {
        const fullLocalPrefix = `${this.LOCAL_PREFIX}${prefix}`;
        const toRemoveLocal: string[] = [];
        for (let i = 0; i < window.localStorage.length; i++) {
          const k = window.localStorage.key(i);
          if (k && k.startsWith(fullLocalPrefix)) {
            toRemoveLocal.push(k);
          }
        }
        for (const k of toRemoveLocal) {
          window.localStorage.removeItem(k);
        }
      } catch {}
    }
  }

  /**
   * Clear entire memory, session, and local cache.
   */
  public clear(): void {
    this.memoryCache.clear();
    this.inFlightRequests.delete("all");
    if (typeof window !== "undefined") {
      try {
        const toRemove: string[] = [];
        for (let i = 0; i < window.sessionStorage.length; i++) {
          const k = window.sessionStorage.key(i);
          if (k && k.startsWith(this.SESSION_PREFIX)) {
            toRemove.push(k);
          }
        }
        for (const k of toRemove) {
          window.sessionStorage.removeItem(k);
        }
      } catch {}

      try {
        const toRemove: string[] = [];
        for (let i = 0; i < window.localStorage.length; i++) {
          const k = window.localStorage.key(i);
          if (k && k.startsWith(this.LOCAL_PREFIX)) {
            toRemove.push(k);
          }
        }
        for (const k of toRemove) {
          window.localStorage.removeItem(k);
        }
      } catch {}
    }
  }

  /**
   * Primary caching primitive:
   * Stale-while-revalidate with in-flight Promise deduplication.
   */
  public async fetch<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: CachedFetchOptions = {}
  ): Promise<T> {
    const {
      staleMs = 30_000,
      ttlMs = 300_000,
      forceRefresh = false,
      persistSession = false,
      persistLocal = false,
    } = options;

    const now = Date.now();
    const existing = forceRefresh ? null : this.get<T>(key);

    // 1. Fresh cache hit: Return immediately (0ms)
    if (existing && now <= existing.staleAt) {
      return existing.data;
    }

    // 2. In-flight deduplication: If identical fetch is already running, coalesce
    const pending = this.inFlightRequests.get(key);
    if (pending) {
      // If we have stale data and request is already in-flight, return stale immediately
      if (existing) {
        return existing.data;
      }
      return pending as Promise<T>;
    }

    // 3. Initiate network request
    const requestPromise = (async () => {
      try {
        const freshData = await fetcher();
        this.set<T>(key, freshData, { staleMs, ttlMs, persistSession, persistLocal });
        return freshData;
      } finally {
        this.inFlightRequests.delete(key);
      }
    })();

    this.inFlightRequests.set(key, requestPromise);

    // 4. Stale-while-revalidate: If we have stale data, return it immediately
    // and let the network request revalidate in background.
    if (existing && !forceRefresh) {
      // Do not await requestPromise, let it resolve in background
      return existing.data;
    }

    // 5. Cache miss or forceRefresh: Await network response
    return requestPromise;
  }

  public subscribe<T>(key: string, listener: Listener<T>): () => void {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key)!.add(listener);

    return () => {
      const set = this.listeners.get(key);
      if (set) {
        set.delete(listener);
        if (set.size === 0) {
          this.listeners.delete(key);
        }
      }
    };
  }

  private notifyListeners<T>(key: string, data: T, meta: CacheMetadata): void {
    const set = this.listeners.get(key);
    if (set) {
      for (const listener of Array.from(set)) {
        try {
          listener(data, meta);
        } catch (err) {
          console.error(`Error in cache listener for key "${key}":`, err);
        }
      }
    }
  }

  public async getOrFetch<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: CachedFetchOptions = {}
  ): Promise<T> {
    return this.fetch<T>(key, fetcher, options);
  }

  public getMetadata(key: string): CacheMetadata {
    const entry = this.get(key);
    if (!entry) {
      return { isCached: false, isStale: true, lastSyncedAt: null };
    }
    return {
      isCached: true,
      isStale: Date.now() > entry.staleAt,
      lastSyncedAt: entry.cachedAt,
    };
  }
}

export const clientCache = new ClientCacheManager();
export const sutraCache = clientCache;

/**
 * Standard TTL Presets (milliseconds)
 */
export const CACHE_TTL = {
  OVERVIEW: { staleMs: 1_200_000, ttlMs: 1_200_000, persistLocal: true },     // 20m fresh, 20m hard, persisted in localStorage
  USER: { staleMs: 300_000, ttlMs: 900_000, persistSession: true },          // 5m fresh, 15m hard
  REPOSITORIES: { staleMs: 120_000, ttlMs: 600_000, persistSession: true },      // 2m fresh, 10m hard
  REPO_DETAIL: { staleMs: 120_000, ttlMs: 600_000, persistSession: true },       // 2m fresh, 10m hard
  BRANCHES: { staleMs: 30_000, ttlMs: 180_000, persistSession: false },          // 30s fresh, 3m hard
  COMMITS: { staleMs: 30_000, ttlMs: 180_000, persistSession: false },           // 30s fresh, 3m hard
  TREE: { staleMs: 60_000, ttlMs: 300_000, persistSession: false },              // 1m fresh, 5m hard
  FILE: { staleMs: 300_000, ttlMs: 3_600_000, persistSession: false },          // 5m fresh, 1h hard
  ISSUES: { staleMs: 60_000, ttlMs: 300_000, persistSession: true },            // 1m fresh, 5m hard
  PULL_REQUESTS: { staleMs: 30_000, ttlMs: 120_000, persistSession: false },     // 30s fresh, 2m hard
  CHECKS: { staleMs: 10_000, ttlMs: 30_000, persistSession: false },             // 10s fresh, 30s hard
} as const;

/**
 * React Hook for Cached Queries with Stale-While-Revalidate semantics.
 */
import { useEffect, useState, useCallback, useRef } from "react";

export function useCachedQuery<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  options: CachedFetchOptions = {}
) {
  const [data, setData] = useState<T | null>(() => {
    if (!key) return null;
    const entry = clientCache.get<T>(key);
    return entry ? entry.data : null;
  });

  const [loading, setLoading] = useState<boolean>(() => {
    if (!key) return false;
    const entry = clientCache.get<T>(key);
    return entry === null;
  });

  const [isStale, setIsStale] = useState<boolean>(() => {
    if (!key) return false;
    const meta = clientCache.getMetadata(key);
    return meta.isStale;
  });

  const [lastSyncedAt, setLastSyncedAt] = useState<number | null>(() => {
    if (!key) return null;
    const meta = clientCache.getMetadata(key);
    return meta.lastSyncedAt;
  });

  const [error, setError] = useState<Error | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const executeFetch = useCallback(
    async (forceRefresh = false) => {
      if (!key) return;
      setError(null);

      const existing = forceRefresh ? null : clientCache.get<T>(key);
      if (!existing) {
        setLoading(true);
      } else {
        setIsStale(Date.now() > existing.staleAt);
      }

      try {
        const result = await clientCache.fetch<T>(key, fetcherRef.current, {
          ...options,
          forceRefresh,
        });
        setData(result);
        const meta = clientCache.getMetadata(key);
        setIsStale(meta.isStale);
        setLastSyncedAt(meta.lastSyncedAt);
      } catch (err: any) {
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        setLoading(false);
      }
    },
    [key, options.staleMs, options.ttlMs, options.persistSession, options.persistLocal]
  );

  useEffect(() => {
    if (!key) {
      setData(null);
      setLoading(false);
      setIsStale(false);
      setLastSyncedAt(null);
      return;
    }

    // Subscribe to background revalidation updates from other components
    const unsubscribe = clientCache.subscribe<T>(key, (updatedData, meta) => {
      setData(updatedData);
      setIsStale(meta.isStale);
      setLastSyncedAt(meta.lastSyncedAt);
      setLoading(false);
    });

    void executeFetch(false);

    return () => {
      unsubscribe();
    };
  }, [key, executeFetch]);

  const refresh = useCallback(() => executeFetch(true), [executeFetch]);

  return { data, loading, isStale, lastSyncedAt, refresh, error };
}

