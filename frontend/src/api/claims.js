import axios from 'axios';
import { mockClaims, mockResults } from '../mocks/mockData';
import { SIGNED_OUT_EVENT, clearSession, readSession } from '../auth/storage';

// Uses the real backend unless VITE_USE_MOCK=true is set in frontend/.env.local
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_URL });
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const MOCK_REVIEWERS = ['Anna Biju', 'Alex O.S', 'Hobhav S Fuzele'];

// A signed-in reviewer's token goes with every request; public endpoints ignore it.
api.interceptors.request.use((config) => {
  const session = readSession();
  if (session?.token) config.headers.Authorization = `Bearer ${session.token}`;
  return config;
});

// A 401 on a reviewer request means the token is missing, invalid or expired: sign out everywhere.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = String(error?.config?.url ?? '');
    if (error?.response?.status === 401 && !url.startsWith('/auth/')) {
      clearSession();
      window.dispatchEvent(new CustomEvent(SIGNED_OUT_EVENT, { detail: error.response.data?.detail }));
    }
    return Promise.reject(error);
  },
);

// The backend returns paths like /results/12_ela.png; those files are served by the backend.
export const assetUrl = (path) => {
  if (!path) return null;
  if (USE_MOCK || /^https?:\/\//.test(path)) return path;
  return `${API_URL}${path}`;
};

// ------------------------------------------------------------------ reviewer sign-in

export async function getReviewers() {
  if (USE_MOCK) { await delay(200); return MOCK_REVIEWERS; }
  return (await api.get('/auth/reviewers')).data;
}

// Returns { token, name, expires_in } (expires_in in seconds). The token is opaque: never parse it.
export async function login(username, password) {
  if (USE_MOCK) {
    await delay(300);
    if (!password) throw Object.assign(new Error('Wrong name or password'), { response: { status: 401, data: { detail: 'Wrong name or password' } } });
    return { token: 'mock-token', name: username, expires_in: 14400 };
  }
  return (await api.post('/auth/login', { username, password })).data;
}

// ------------------------------------------------------------------ claimants (public)

// Returns the claim, including tracking_code (shown to the claimant once)
export async function createClaim(claim) {
  if (USE_MOCK) { await delay(300); return { id: 99, ...claim, tracking_code: 'K7Q2-MX9P' }; }
  return (await api.post('/claims', claim)).data;
}

export async function uploadImages(claimId, files, onProgress) {
  if (USE_MOCK) {
    for (let p = 0; p <= 100; p += 20) { onProgress?.(p); await delay(150); }
    return files.map((f, i) => ({ image_id: i + 1, url: '/mock/claim_photo.svg', duplicate_of: null }));
  }
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  const res = await api.post(`/claims/${claimId}/images`, form, {
    onUploadProgress: (e) => onProgress?.(Math.round((100 * e.loaded) / (e.total || 1))),
  });
  return res.data;
}

export async function analyzeClaim(claimId) {
  if (USE_MOCK) { await delay(800); return { claim_id: claimId, overall_risk: 'high', risk_score: 0.81 }; }
  return (await api.post(`/claims/${claimId}/analyze`)).data;
}

// Public status for claimants: { claim_id, claimant_name, incident_date, status, message, steps: [{ step, done, time }] }
export async function getClaimStatus(claimId, code) {
  if (USE_MOCK) {
    await delay(400);
    const c = mockClaims.find((x) => x.id === Number(claimId));
    if (!c || !code.trim()) {
      throw Object.assign(new Error('not found'), { response: { status: 404, data: { detail: 'No claim found with that number and code' } } });
    }
    const decided = Boolean(c.reviewer_decision);
    const review = decided || ['medium', 'high'].includes(c.overall_risk);
    return {
      claim_id: c.id, claimant_name: c.claimant_name, incident_date: c.incident_date,
      status: decided ? (c.reviewer_decision === 'approved' ? 'Approved' : 'Needs further review')
        : review ? 'Under review' : c.overall_risk ? 'Being processed' : 'Received',
      message: review && !decided ? 'A reviewer is looking at your claim.' : 'Your claim is moving ahead.',
      steps: [
        { step: 'Received', done: true, time: c.created_at },
        { step: 'Photos checked', done: Boolean(c.overall_risk), time: null },
        { step: 'Under review', done: review, time: null },
        { step: 'Decision', done: decided, time: null },
      ],
    };
  }
  return (await api.get(`/claims/${claimId}/status`, { params: { code } })).data;
}

// ------------------------------------------------------------------ reviewers (token required)

// risk: 'low' | 'medium' | 'high' | undefined (all claims)
export async function listClaims(risk) {
  if (USE_MOCK) {
    await delay(300);
    return risk ? mockClaims.filter((c) => c.overall_risk === risk) : mockClaims;
  }
  return (await api.get('/claims', { params: risk ? { risk } : {} })).data;
}

export async function getResults(claimId) {
  if (USE_MOCK) { await delay(300); return mockResults[claimId] ?? mockResults[1]; }
  return (await api.get(`/claims/${claimId}/results`)).data;
}

export async function getReviewQueue() {
  if (USE_MOCK) {
    await delay(300);
    return mockClaims
      .filter((c) => ['medium', 'high'].includes(c.overall_risk) && !c.reviewer_decision)
      .map((c) => ({ claim_id: c.id, claimant_name: c.claimant_name, overall_risk: c.overall_risk, risk_score: c.risk_score }));
  }
  return (await api.get('/review-queue')).data;
}

// decision: 'approved' | 'escalated'; the token is added by the request interceptor
export async function submitDecision(claimId, decision, note, session) {
  if (USE_MOCK) {
    await delay(300);
    const result = mockResults[claimId];
    if (result) {
      Object.assign(result, { reviewer_decision: decision, reviewer_note: note, reviewer_name: session?.name ?? null, decided_at: new Date().toISOString() });
    }
    const claim = mockClaims.find((c) => c.id === Number(claimId));
    if (claim) claim.reviewer_decision = decision;
    return { claim_id: Number(claimId), decision, note };
  }
  return (await api.patch(`/claims/${claimId}/decision`, { decision, note })).data;
}
