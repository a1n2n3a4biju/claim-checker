import axios from 'axios';
import { mockClaims, mockResults } from '../mocks/mockData';

// Set VITE_USE_MOCK=false in frontend/.env to use the real backend.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({ baseURL: API_URL });
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// The backend returns paths like /results/12_ela.png; those files are served by the backend.
export const assetUrl = (path) => {
  if (!path) return null;
  if (USE_MOCK || /^https?:\/\//.test(path)) return path;
  return `${API_URL}${path}`;
};

export async function listClaims() {
  if (USE_MOCK) { await delay(300); return mockClaims; }
  return (await api.get('/claims')).data;
}

export async function createClaim(claim) {
  if (USE_MOCK) { await delay(300); return { id: 99, ...claim }; }
  return (await api.post('/claims', claim)).data;
}

export async function uploadImages(claimId, files, onProgress) {
  if (USE_MOCK) {
    for (let p = 0; p <= 100; p += 20) { onProgress?.(p); await delay(150); }
    return files.map((f, i) => ({ image_id: i + 1, url: '/mock/claim_photo.jpg', duplicate_of: null }));
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


// decision: 'approved' | 'escalated'
export async function submitDecision(claimId, decision, note) {
  if (USE_MOCK) {
    await delay(300);
    const result = mockResults[claimId];
    if (result) { result.reviewer_decision = decision; result.reviewer_note = note; }
    const claim = mockClaims.find((c) => c.id === Number(claimId));
    if (claim) claim.reviewer_decision = decision;
    return { claim_id: Number(claimId), decision, note };
  }
  return (await api.patch(`/claims/${claimId}/decision`, { decision, note })).data;
}