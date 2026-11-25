import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { login as apiLogin } from '../api/claims';
import { SIGNED_OUT_EVENT, clearSession, readSession, saveSession } from './storage';

// Reviewer sign-in state, shared by the header, the sign-in dialog and the reviewer-only pages.

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(readSession);
  const [dialog, setDialog] = useState({ open: false, redirect: null });
  const [notice, setNotice] = useState('');        // why the reviewer was signed out, shown on the next page

  // The API layer announces a rejected token (401) on any reviewer request
  useEffect(() => {
    const onSignedOut = (e) => {
      setSession(null);
      setNotice(e.detail ? `${e.detail}. Please sign in again.` : 'Your sign-in has ended. Please sign in again.');
    };
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut);
  }, []);

  const signIn = useCallback(async (username, password) => {
    const res = await apiLogin(username, password);
    const next = { token: res.token, name: res.name, expiresAt: Date.now() + res.expires_in * 1000 };
    saveSession(next);
    setSession(next);
    setNotice('');
    return next;
  }, []);

  const signOut = useCallback((reason) => {
    clearSession();
    setSession(null);
    setNotice(typeof reason === 'string' ? reason : '');
  }, []);

  const value = useMemo(() => ({
    session: session && session.expiresAt > Date.now() ? session : null,
    notice,
    signIn,
    signOut,
    dialogOpen: dialog.open,
    redirectTo: dialog.redirect,
    // openSignIn('/claims') opens the dialog and goes there after signing in; used as an onClick it just opens
    openSignIn: (redirect) => setDialog({ open: true, redirect: typeof redirect === 'string' ? redirect : null }),
    closeSignIn: () => setDialog({ open: false, redirect: null }),
  }), [session, notice, signIn, signOut, dialog]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
