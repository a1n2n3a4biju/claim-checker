import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getMe, login as apiLogin, register as apiRegister } from '../api';
import { SIGNED_OUT_EVENT } from '../api/client';
import { clearToken, readToken, saveToken } from './storage';

// The signed-in user, shared by the header, the login page and the role-protected pages.
const AuthContext = createContext(null);

// Each role's home page (team doc, M1 step 2)
export const HOME = {
  claimant: '/my/claims',
  assessor: '/assessor/claims',
  insurer: '/insurer/claims',
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // 'checking' while a saved token is restored with GET /me after a page refresh
  const [status, setStatus] = useState(() => (readToken() ? 'checking' : 'ready'));
  const [notice, setNotice] = useState('');     // why the user was signed out, shown on the login page

  useEffect(() => {
    if (status !== 'checking') return;
    getMe()
      .then((me) => setUser({ id: me.id, name: me.name, role: me.role }))
      .catch(() => clearToken())
      .finally(() => setStatus('ready'));
  }, [status]);

  // The API layer announces a 401 on any request
  useEffect(() => {
    const onSignedOut = (e) => {
      setUser(null);
      setNotice(e.detail || 'Your sign-in has ended. Please sign in again.');
    };
    window.addEventListener(SIGNED_OUT_EVENT, onSignedOut);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, onSignedOut);
  }, []);

  const signIn = useCallback(async (email, password) => {
    const res = await apiLogin(email, password);
    saveToken(res.token);
    setUser(res.user);
    setNotice('');
    return res.user;
  }, []);

  // New customer account: signed in straight away
  const signUp = useCallback(async (name, email, password) => {
    const res = await apiRegister(name, email, password);
    saveToken(res.token);
    setUser(res.user);
    setNotice('');
    return res.user;
  }, []);

  const signOut = useCallback(() => {
    clearToken();
    setUser(null);
    setNotice('');
  }, []);

  const value = useMemo(() => ({ user, ready: status === 'ready', notice, signIn, signUp, signOut }),
    [user, status, notice, signIn, signUp, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
