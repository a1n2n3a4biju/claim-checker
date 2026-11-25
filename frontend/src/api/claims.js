import axios from 'axios';
import { mockClaims, mockResults } from '../mocks/mockData';

// Uses the real backend unless VITE_USE_MOCK=true is set in frontend/.env.local
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_URL });
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const MOCK_REVIEWERS = ['Anna Biju', 'Alex O.S', 'Hobhav S Fuzele'];

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

// ------------------------------------------------------------------ claims

// risk: 'low' | 'medium' | 'high' | undefined (all claims)
export async function listClaims(risk) {
  if (USE_MOCK) {
    await delay(300);
    return risk ? mockClaims.filter((c) => c.overall_risk === risk) : mockClaims;
  }
  return (await api.get('/claims', { params: risk ? { risk } : {} })).data;
}

export async function createClaim(claim) {
  if (USE_MOCK) { await delay(300); return { id: 99, ...claim }; }
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

// decision: 'approved' | 'escalated'; session: { token, name } from the reviewer sign-in
export async function submitDecision(claimId, decision, note, session) {
  if (USE_MOCK) {
    await delay(300);
    const decidedAt = new Date().toISOString();
    const result = mockResults[claimId];
    if (result) {
      Object.assign(result, { reviewer_decision: decision, reviewer_note: note, reviewer_name: session?.name ?? null, decided_at: decidedAt });
    }
    const claim = mockClaims.find((c) => c.id === Number(claimId));
    if (claim) claim.reviewer_decision = decision;
    return { claim_id: Number(claimId), decision, note };
  }
  return (await api.patch(
    `/claims/${claimId}/decision`,
    { decision, note },
    { headers: session?.token ? { Authorization: `Bearer ${session.token}` } : {} },
  )).data;
}
