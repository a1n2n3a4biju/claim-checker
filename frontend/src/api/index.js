// Every backend call lives here, one small function per endpoint (contract section 3.1).
// Pages never call fetch or axios directly: if the contract changes, only this file changes.
// With VITE_USE_MOCK=true each function returns sample data from ../mocks/mockServer.js instead.
import { USE_MOCK, http } from './client';
import * as mock from '../mocks/mockServer';

export { API_URL, ApiError, USE_MOCK, assetUrl, errorText } from './client';

const data = (promise) => promise.then((r) => r.data);

// Claimant pages never show risk information, even if a field appears by mistake.
const RISK_KEYS = ['risk_score', 'risk_level', 'reasons', 'fraud_flag', 'images', 'modules', 'heatmap_url', 'suggested_payout'];
export function stripRisk(value) {
  if (Array.isArray(value)) return value.map(stripRisk);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).filter(([k]) => !RISK_KEYS.includes(k)).map(([k, v]) => [k, stripRisk(v)]));
  }
  return value;
}

// ------------------------------------------------------------------ anyone

// Returns { token, user: { id, name, role } }
export const login = (email, password) =>
  USE_MOCK ? mock.login(email, password) : data(http.post('/auth/login', { email, password }));

// New customer account (always a claimant). Returns { token, user } like login.
export const register = (name, email, password) =>
  USE_MOCK ? mock.register(name, email, password) : data(http.post('/auth/register', { name, email, password }));

// The signed-in user; used to restore the session after a page refresh
export const getMe = () => (USE_MOCK ? mock.getMe() : data(http.get('/me')));

// ------------------------------------------------------------------ claimant

export const getMyPolicies = () => (USE_MOCK ? mock.getMyPolicies() : data(http.get('/me/policies')));

// claim: { vehicle_id, incident_date, incident_time, location, severity, description }
export const createClaim = (claim) =>
  (USE_MOCK ? mock.createClaim(claim) : data(http.post('/claims', claim))).then(stripRisk);

// JPEG photos, field name "files". The photo checks start after the upload.
export function uploadImages(claimId, files, onProgress) {
  if (USE_MOCK) return mock.uploadImages(claimId, files, onProgress);
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  return data(http.post(`/claims/${claimId}/images`, form, {
    onUploadProgress: (e) => onProgress?.(Math.round((100 * e.loaded) / (e.total || 1))),
  }));
}

export const getMyClaims = () =>
  (USE_MOCK ? mock.getMyClaims() : data(http.get('/me/claims'))).then(stripRisk);

export const getMyClaim = (id) =>
  (USE_MOCK ? mock.getMyClaim(id) : data(http.get(`/me/claims/${id}`))).then(stripRisk);

// Reply to a more-info request: a note and optional photos
export function replyToInfoRequest(id, note, files = []) {
  if (USE_MOCK) return mock.reply(id, note, files).then(stripRisk);
  const form = new FormData();
  form.append('note', note);
  files.forEach((file) => form.append('files', file));
  return data(http.post(`/claims/${id}/reply`, form)).then(stripRisk);
}

// ------------------------------------------------------------------ assessor

export const getAssessorClaims = () => (USE_MOCK ? mock.getAssessorClaims() : data(http.get('/assessor/claims')));

export const getAssessorClaim = (id) => (USE_MOCK ? mock.getAssessorClaim(id) : data(http.get(`/assessor/claims/${id}`)));

// items: [{ kind: 'part' | 'labour', description, quantity, unit_price }]; the backend calculates the total
export const submitQuotation = (id, items, note) =>
  USE_MOCK ? mock.submitQuotation(id, items, note) : data(http.post(`/claims/${id}/quotation`, { items, note }));

export const getPriceList = () => (USE_MOCK ? mock.getPriceList() : data(http.get('/price-list')));

// ------------------------------------------------------------------ insurer

// filters: { status, risk } (both optional)
export function getInsurerClaims({ status, risk } = {}) {
  const params = {};
  if (status) params.status = status;
  if (risk) params.risk = risk;
  return USE_MOCK ? mock.getInsurerClaims(params) : data(http.get('/insurer/claims', { params }));
}

export const getInsurerClaim = (id) => (USE_MOCK ? mock.getInsurerClaim(id) : data(http.get(`/insurer/claims/${id}`)));

export const startReview = (id) => (USE_MOCK ? mock.startReview(id) : data(http.post(`/claims/${id}/start-review`)));

export const requestInfo = (id, message) =>
  USE_MOCK ? mock.requestInfo(id, message) : data(http.post(`/claims/${id}/request-info`, { message }));

// outcome: 'approved' (amount required) | 'rejected' | 'further_review' (note required)
export const submitDecision = (id, outcome, amount, note) => {
  const body = { outcome, note: note ?? '' };
  if (outcome === 'approved') body.amount = amount;
  return USE_MOCK ? mock.submitDecision(id, body) : data(http.post(`/claims/${id}/decision`, body));
};

export const settleClaim = (id) => (USE_MOCK ? mock.settle(id) : data(http.post(`/claims/${id}/settle`)));
