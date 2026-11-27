import { createContext, useContext } from 'react';

// The signed-in user, shared by the header, the login page and the role-protected pages.
// Kept apart from AuthContext.jsx so that file exports only a component (needed for fast refresh).
export const AuthContext = createContext(null);

// Each role's home page (team doc, M1 step 2)
export const HOME = {
  claimant: '/my/claims',
  assessor: '/assessor/claims',
  insurer: '/insurer/claims',
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
