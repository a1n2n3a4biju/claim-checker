import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { login as apiLogin } from '../api/claims';

// Reviewer sign-in state, shared by the navigation rail, the sign-in dialog and the review panel.
// The token is kept in sessionStorage: it survives a page reload but not closing the browser.

const STORAGE_KEY = 'claimChecker.reviewer';
const AuthContext = createContext(null);

function loadSession() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY));
    if (saved?.token && saved.expiresAt > Date.now()) return saved;
  } catch {
    // ignore unreadable storage
  }
  sessionStorage.removeItem(STORAGE_KEY);
  return null;
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(loadSession);
  const [dialogOpen, setDialogOpen] = useState(false);

  const signIn = useCallback(async (username, password) => {
    const res = await apiLogin(username, password);
    const next = { token: res.token, name: res.name, expiresAt: Date.now() + res.expires_in * 1000 };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setSession(next);
    return next;
  }, []);

  const signOut = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    setSession(null);
  }, []);

  const value = useMemo(() => ({
    // a session past its expiry counts as signed out; the backend would reject it anyway
    session: session && session.expiresAt > Date.now() ? session : null,
    signIn,
    signOut,
    dialogOpen,
    openSignIn: () => setDialogOpen(true),
    closeSignIn: () => setDialogOpen(false),
  }), [session, signIn, signOut, dialogOpen]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
