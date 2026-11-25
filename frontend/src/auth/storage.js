// Where the reviewer's sign-in is kept: sessionStorage survives a page reload but not closing the browser.
export const STORAGE_KEY = 'claimProof.reviewer';
export const SIGNED_OUT_EVENT = 'claimproof:signed-out';

export function readSession() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY));
    if (saved?.token && saved.expiresAt > Date.now()) return saved;
  } catch {
    // unreadable storage counts as signed out
  }
  return null;
}

export function saveSession(session) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession() {
  sessionStorage.removeItem(STORAGE_KEY);
}
