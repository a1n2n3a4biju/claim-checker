import axios from 'axios';
import { mockClaims, mockResults } from '../mocks/mockData';

// Set VITE_USE_MOCK=false in frontend/.env to use the real backend.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000' });
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function listClaims() {
  if (USE_MOCK) { await delay(300); return mockClaims; }
  return (await api.get('/claims')).data;
}

export async function createClaim(claim) {
  if (USE_MOCK) { await delay(300); return { id: 99, ...claim, created_at: new Date().toISOString() }; }
  return (await api.post('/claims', claim)).data;
}

export async function uploadImages(claimId, files, onProgress) {
  if (USE_MOCK) {
    for (let p = 0; p <= 100; p += 20) { onProgress?.(p); await delay(150); }
    return files.map((f, i) => ({ image_id: i + 1, filename: f.name }));
  }
  const form = new FormData();
  files.forEach((file) => form.append('files', file));   // field name to confirm with M3
  const res = await api.post(`/claims/${claimId}/images`, form, {
    onUploadProgress: (e) => onProgress?.(Math.round((100 * e.loaded) / (e.total || 1))),
  });
  return res.data;
}

export async function analyzeClaim(claimId) {
  if (USE_MOCK) { await delay(800); return { claim_id: claimId, status: 'analyzed' }; }
  return (await api.post(`/claims/${claimId}/analyze`)).data;
}

export async function getResults(claimId) {
  if (USE_MOCK) { await delay(300); return mockResults[claimId] ?? mockResults[1]; }
  return (await api.get(`/claims/${claimId}/results`)).data;
}

export async function submitDecision(claimId, decision, note) {
  if (USE_MOCK) { await delay(300); return { claim_id: claimId, reviewer_decision: decision, reviewer_note: note }; }
  return (await api.patch(`/claims/${claimId}/decision`, { reviewer_decision: decision, reviewer_note: note })).data;
}