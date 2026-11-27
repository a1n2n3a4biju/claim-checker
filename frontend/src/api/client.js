import axios from 'axios';
import { clearToken, readToken } from '../auth/storage';

// Uses the real backend unless VITE_USE_MOCK=true is set in frontend/.env.local
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Fired when the backend says the sign-in is missing or expired (401); AuthContext listens.
export const SIGNED_OUT_EVENT = 'claimproof:signed-out';

// Every API function throws this, so pages handle errors the same way (contract 2.7).
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export const http = axios.create({ baseURL: API_URL });

// The token goes with every request automatically.
http.interceptors.request.use((config) => {
  const token = readToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status ?? 0;
    const raw = error?.response?.data?.detail;
    const detail = typeof raw === 'string' ? raw
      : status === 0 ? `Can't reach the server at ${API_URL}. Is the backend running?`
      : 'Something went wrong. Please try again.';
    const url = String(error?.config?.url ?? '');
    // 401: clear the token and go to the login page (but a wrong password just shows the message)
    if (status === 401 && !url.startsWith('/auth/')) signedOut(detail);
    return Promise.reject(new ApiError(status, detail));
  },
);

export function signedOut(detail) {
  clearToken();
  window.dispatchEvent(new CustomEvent(SIGNED_OUT_EVENT, { detail }));
}

// The backend returns paths like /uploads/21.jpg; those files are served by the backend.
export const assetUrl = (path) => {
  if (!path) return null;
  if (USE_MOCK || /^https?:\/\//.test(path)) return path;
  return `${API_URL}${path}`;
};

// What a page should say for an error (contract 2.7)
export function errorText(err) {
  if (err?.status === 403) return "You don't have access to this";
  if (err?.status === 404) return 'Not found';
  return err?.detail || err?.message || 'Something went wrong. Please try again.';
}
