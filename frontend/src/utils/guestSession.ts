/**
 * NutriPod Guest Session Management
 * Manages anonymous guest session lifecycle for Recommendation & Meal Planner Service (:8003).
 *
 * Privacy & Security Guarantees:
 * - Purely anonymous UUID tokens; never contains personally identifiable information.
 * - Stored exclusively in browser localStorage (no cookies, no cross-site leakage).
 * - Transmitted exclusively in the X-Guest-Session-ID header to Planner Service (:8003).
 * - Never sent to Recipe Service (:8002) or Profile Service (:8001).
 * - Never exposed in user-facing UI or application logs.
 */

import { plannerClient } from '../api/plannerClient';
import { GuestSession } from '../api/types/planner';

export const GUEST_SESSION_STORAGE_KEY = 'foodflow_guest_session';

export interface StoredGuestSession {
  sessionId: string;
  expiresAt: string;
  createdAt: string;
}

/**
 * Retrieve the current guest session from localStorage if present and structurally valid.
 */
export function getStoredGuestSession(): StoredGuestSession | null {
  try {
    const raw = localStorage.getItem(GUEST_SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.sessionId !== 'string' || !parsed.sessionId.trim()) {
      return null;
    }
    return {
      sessionId: parsed.sessionId.trim(),
      expiresAt: parsed.expiresAt || '',
      createdAt: parsed.createdAt || '',
    };
  } catch {
    return null;
  }
}

/**
 * Persist an active guest session to localStorage.
 */
export function saveGuestSession(session: GuestSession): void {
  try {
    const stored: StoredGuestSession = {
      sessionId: session.session_id,
      expiresAt: session.expires_at,
      createdAt: session.created_at,
    };
    localStorage.setItem(GUEST_SESSION_STORAGE_KEY, JSON.stringify(stored));
  } catch {
    // Gracefully handle browser storage quota or privacy mode exceptions
  }
}

/**
 * Remove any stored guest session from localStorage.
 */
export function clearGuestSession(): void {
  try {
    localStorage.removeItem(GUEST_SESSION_STORAGE_KEY);
  } catch {
    // Gracefully handle storage exceptions
  }
}

/**
 * Check whether a session timestamp is expired (with a 60-second safety margin).
 */
export function isSessionExpired(expiresAt?: string): boolean {
  if (!expiresAt) return false;
  try {
    const expiryTime = new Date(expiresAt).getTime();
    if (isNaN(expiryTime)) return false;
    return Date.now() >= expiryTime - 60000;
  } catch {
    return false;
  }
}

// In-flight promise to prevent concurrent duplicate session creations
let pendingSessionCreationPromise: Promise<string> | null = null;

/**
 * Retrieve an existing active guest session ID or initialize a new one.
 * Thread-safe: collapses simultaneous calls into a single in-flight network request.
 */
export async function getOrCreateGuestSession(): Promise<string> {
  const existing = getStoredGuestSession();
  if (existing && !isSessionExpired(existing.expiresAt)) {
    return existing.sessionId;
  }

  // Prevent multiple simultaneous session creations
  if (pendingSessionCreationPromise) {
    return pendingSessionCreationPromise;
  }

  pendingSessionCreationPromise = (async () => {
    try {
      const session = await plannerClient.createGuestSession();
      saveGuestSession(session);
      return session.session_id;
    } finally {
      pendingSessionCreationPromise = null;
    }
  })();

  return pendingSessionCreationPromise;
}

/**
 * Recover from an expired session by clearing invalid cached state and provisioning a fresh session.
 */
export async function recoverExpiredGuestSession(): Promise<string> {
  clearGuestSession();
  return getOrCreateGuestSession();
}

