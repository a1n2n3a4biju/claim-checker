// Mock backend for VITE_USE_MOCK=true. Follows the contract (sections 2 and 3) so that switching
// to the real backend "just works". Data lives in memory and resets on page refresh.
// Demo accounts: claimant1..30, assessor1 and insurer1 @demo.in (same as the seed), any non-empty password.
import { ApiError, signedOut } from '../api/client';
import { readToken } from '../auth/storage';
import { STATUSES } from '../utils/status';

const PHOTO = '/mock/claim_photo.svg';
const delay = (ms = 250) => new Promise((resolve) => setTimeout(resolve, ms));
const clone = (x) => JSON.parse(JSON.stringify(x));
const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, '+00:00');
const fail = (status, detail) => { throw new ApiError(status, detail); };

const CLAIMANT_NAMES = [
  'Ravi Kumar', 'Meena Iyer', 'Arjun Reddy', 'Lakshmi Narayanan', 'Karthik Raja', 'Divya Shankar', 'Vignesh Murali',
  'Anitha Raman', 'Prakash Rao', 'Sangeetha Pillai', 'Rahul Menon', 'Deepa Krishnan', 'Senthil Kumar', 'Nandini Gopal',
  'Manoj Varma', 'Revathi Sundar', 'Ashok Natarajan', 'Kavitha Ramesh', 'Ganesh Iyer', 'Preethi Balaji',
  'Harish Chandran', 'Swathi Mohan', 'Bala Subramanian', 'Janani Venkat', 'Mohan Das', 'Pooja Hegde',
  'Sathish Kannan', 'Uma Maheswari', 'Vinod Nair', 'Yamuna Devi',
];
const ASSESSOR = 31;
const INSURER = 32;
const users = [
  ...CLAIMANT_NAMES.map((name, i) => ({ id: i + 1, email: `claimant${i + 1}@demo.in`, name, role: 'claimant' })),
  { id: ASSESSOR, email: 'assessor1@demo.in', name: 'Suresh Babu', role: 'assessor' },
  { id: INSURER, email: 'insurer1@demo.in', name: 'Priya Menon', role: 'insurer' },
];
const userById = (id) => users.find((u) => u.id === id);
const person = (u) => (u ? `${u.name} (${u.role})` : 'System');

const policies = [
  { id: 4, user_id: 1, policy_number: 'POL-2026-0041', start_date: '2026-01-01', end_date: '2026-12-31',
    premium: 12500, deductible: 2000, sum_insured: 400000,
    vehicles: [{ id: 7, registration: 'TN 37 AB 1234', make: 'Maruti', model: 'Swift', year: 2021 },
               { id: 8, registration: 'TN 38 CD 5678', make: 'Hyundai', model: 'i20', year: 2023 }] },
  { id: 5, user_id: 2, policy_number: 'POL-2025-0107', start_date: '2025-11-01', end_date: '2026-10-31',
    premium: 9800, deductible: 1500, sum_insured: 300000,
    vehicles: [{ id: 9, registration: 'TN 66 EF 9012', make: 'Honda', model: 'City', year: 2019 }] },
  // claimants 3-30: one 2026 policy and one car each
  ...CLAIMANT_NAMES.slice(2).map((_, k) => {
    const i = k + 3;
    return { id: 100 + i, user_id: i, policy_number: `POL-2026-${String(i).padStart(4, '0')}`,
             start_date: '2026-01-01', end_date: '2026-12-31', premium: 8000 + 250 * i,
             deductible: [1000, 1500, 2000, 2500][i % 4], sum_insured: [250000, 300000, 400000, 500000][i % 4],
             vehicles: [{ id: 100 + i, registration: `TN 37 A${String.fromCharCode(65 + (i % 26))} ${1000 + 37 * i}`,
                          make: 'Maruti', model: 'Swift', year: 2018 + (i % 7) }] };
  }),
];
const findVehicle = (id) => {
  for (const p of policies) {
    const v = p.vehicles.find((x) => x.id === Number(id));
    if (v) return { vehicle: v, policy: p };
  }
  return {};
};

const priceList = [
  { kind: 'part', description: 'Rear bumper (hatchback)', unit_price: 8500 },
  { kind: 'part', description: 'Front bumper (hatchback)', unit_price: 7800 },
  { kind: 'part', description: 'Headlamp assembly', unit_price: 6200 },
  { kind: 'part', description: 'Tail lamp assembly', unit_price: 3400 },
  { kind: 'part', description: 'Front fender', unit_price: 4200 },
  { kind: 'part', description: 'Outer rear view mirror', unit_price: 2900 },
  { kind: 'labour', description: 'Paint, per panel', unit_price: 3500 },
  { kind: 'labour', description: 'Fitting, per hour', unit_price: 800 },
  { kind: 'labour', description: 'Denting, per panel', unit_price: 1500 },
];

const moduleSet = (scores) => Object.entries(scores).map(([module, score]) => ({
  module, score, flags: score > 0.7 ? [`${module.replace(/_/g, ' ')} found an unusual region`] : [], artifacts: {},
}));

let nextClaimId = 13;
let nextImageId = 30;

function makeClaim(c) {
  return {
    incident_time: '10:00', location: 'Coimbatore', severity: 'moderate', description: 'Damage to the car',
    decision: null, approved_amount: null, decision_note: '', info_request: null, quotation: null,
    risk_level: null, risk_score: null, fraud_flag: false, reasons: [], images: [], assessor_id: null,
    history: [], ...c,
  };
}

const t = (d, h) => `2026-11-${String(d).padStart(2, '0')}T${String(h).padStart(2, '0')}:00:00+00:00`;
const hist = (moves) => moves.map(([from, to, by, at, note = '']) => ({ from, to, by, at, note }));

const claims = [
  makeClaim({
    id: 12, claimant_id: 1, vehicle_id: 7, incident_date: '2026-11-15', incident_time: '14:30',
    location: 'Avinashi Road, Coimbatore', description: 'Rear bumper hit while parked', created_at: t(15, 9),
    status: 'under_review', risk_level: 'high', risk_score: 0.91, fraud_flag: true, assessor_id: ASSESSOR,
    reasons: ['AI detector 1 rates this photo as very likely AI-generated', 'Lighting on the bumper does not match the scene'],
    images: [{ image_id: 21, url: PHOTO, risk_level: 'high', risk_score: 0.91,
               modules: moduleSet({ ela: 0.42, noise: 0.38, copy_move: 0.1, jpeg: 0.2, ai_detector_1: 0.97, ai_detector_2: 0.88 }) }],
    quotation: { total: 38500, note: 'Bumper cracked, needs replacement', assessor: 'Suresh Babu (assessor)',
                 items: [{ kind: 'part', description: 'Rear bumper', quantity: 1, unit_price: 8500, amount: 8500 },
                         { kind: 'part', description: 'Tail lamp assembly', quantity: 2, unit_price: 3400, amount: 6800 },
                         { kind: 'labour', description: 'Paint and fitting', quantity: 29, unit_price: 800, amount: 23200 }] },
    history: hist([[null, 'submitted', 'Ravi Kumar (claimant)', t(15, 9), 'Claim submitted'],
                   ['submitted', 'photos_checked', 'System', t(15, 9), '1 photo checked'],
                   ['photos_checked', 'awaiting_assessment', 'System', t(15, 9), 'Assigned to Suresh Babu'],
                   ['awaiting_assessment', 'assessed', 'Suresh Babu (assessor)', t(17, 11), 'Bumper cracked, needs replacement'],
                   ['assessed', 'under_review', 'Priya Menon (insurer)', t(18, 10), 'Review started']]),
  }),
  makeClaim({
    id: 11, claimant_id: 1, vehicle_id: 8, incident_date: '2026-11-02', created_at: t(2, 8),
    location: 'Gandhipuram, Coimbatore', description: 'Side mirror broken',
    status: 'settled', risk_level: 'low', risk_score: 0.28, assessor_id: ASSESSOR, decision: 'approved', approved_amount: 4500,
    images: [{ image_id: 20, url: PHOTO, risk_level: 'low', risk_score: 0.28,
               modules: moduleSet({ ela: 0.3, noise: 0.4, copy_move: 0, jpeg: 0.05, ai_detector_1: 0.01, ai_detector_2: 0.02 }) }],
    quotation: { total: 6500, note: 'Mirror replacement', assessor: 'Suresh Babu (assessor)',
                 items: [{ kind: 'part', description: 'Outer rear view mirror', quantity: 1, unit_price: 2900, amount: 2900 },
                         { kind: 'labour', description: 'Fitting, per hour', quantity: 2, unit_price: 800, amount: 1600 },
                         { kind: 'labour', description: 'Paint, per panel', quantity: 1, unit_price: 2000, amount: 2000 }] },
    history: hist([[null, 'submitted', 'Ravi Kumar (claimant)', t(2, 8)], ['submitted', 'photos_checked', 'System', t(2, 8)],
                   ['photos_checked', 'awaiting_assessment', 'System', t(2, 8), 'Assigned to Suresh Babu'],
                   ['awaiting_assessment', 'assessed', 'Suresh Babu (assessor)', t(3, 12)],
                   ['assessed', 'under_review', 'Priya Menon (insurer)', t(4, 9)],
                   ['under_review', 'decided', 'Priya Menon (insurer)', t(4, 10), 'approved: Matches quotation'],
                   ['decided', 'settled', 'Priya Menon (insurer)', t(6, 15), 'Paid 4500']]),
  }),
  makeClaim({
    id: 10, claimant_id: 2, vehicle_id: 9, incident_date: '2026-10-03', created_at: t(1, 7),
    location: 'RS Puram, Coimbatore', severity: 'minor', description: 'Dent on the front door',
    status: 'awaiting_assessment', risk_level: 'medium', risk_score: 0.52, assessor_id: ASSESSOR,
    reasons: ['Error level analysis found an area that compresses differently'],
    images: [{ image_id: 19, url: PHOTO, risk_level: 'medium', risk_score: 0.52,
               modules: moduleSet({ ela: 0.74, noise: 0.5, copy_move: 0.2, jpeg: 0.3, ai_detector_1: 0.05, ai_detector_2: 0.04 }) }],
    history: hist([[null, 'submitted', 'Meena Iyer (claimant)', t(1, 7)], ['submitted', 'photos_checked', 'System', t(1, 7)],
                   ['photos_checked', 'awaiting_assessment', 'System', t(1, 7), 'Assigned to Suresh Babu']]),
  }),
];

// ------------------------------------------------------------------ helpers

function me() {
  const token = readToken() ?? '';
  const user = token.startsWith('mock:') ? userById(Number(token.slice(5))) : null;
  if (!user) {
    signedOut('Please sign in');
    fail(401, 'Please sign in');
  }
  return user;
}

function as(...roles) {
  const user = me();
  if (!roles.includes(user.role)) fail(403, "You don't have access to this");
  return user;
}

function findClaim(id) {
  return claims.find((c) => c.id === Number(id)) ?? fail(404, 'Not found');
}

const ALLOWED = {
  'null>submitted': 'claimant', 'submitted>photos_checked': 'system', 'photos_checked>awaiting_assessment': 'system',
  'awaiting_assessment>assessed': 'assessor', 'assessed>under_review': 'insurer',
  'under_review>more_info_requested': 'insurer', 'more_info_requested>under_review': 'claimant',
  'under_review>decided': 'insurer', 'decided>settled': 'insurer',
};

function move(claim, to, user, note = '') {
  const from = claim.status ?? null;
  const who = ALLOWED[`${from}>${to}`];
  if (!who) fail(409, `A claim can't move from '${STATUSES[from]?.staff ?? 'new'}' to '${STATUSES[to].staff}'.`);
  if (who !== (user?.role ?? 'system')) fail(403, "You don't have access to this");
  claim.status = to;
  claim.history.push({ from, to, by: person(user), at: nowIso(), note });
}

const vehicleOf = (c) => findVehicle(c.vehicle_id).vehicle;
const policyOf = (c) => findVehicle(c.vehicle_id).policy;

function claimantView(c) {
  const v = vehicleOf(c);
  return {
    id: c.id, status: c.status, status_label: STATUSES[c.status].claimant,
    vehicle: { registration: v.registration, make: v.make, model: v.model },
    incident_date: c.incident_date, incident_time: c.incident_time, location: c.location, severity: c.severity,
    description: c.description, created_at: c.created_at,
    quotation_total: c.quotation?.total ?? null, decision: c.decision, approved_amount: c.approved_amount,
    info_request: c.status === 'more_info_requested' ? c.info_request : null,
    timeline: c.history.map((h) => ({ status: h.to, label: STATUSES[h.to].claimant, at: h.at })),
  };
}

function staffSummary(c) {
  const v = vehicleOf(c);
  return {
    id: c.id, status: c.status, status_label: STATUSES[c.status].staff, claimant: userById(c.claimant_id).name,
    vehicle: { registration: v.registration, make: v.make, model: v.model }, incident_date: c.incident_date,
    severity: c.severity, created_at: c.created_at, risk_level: c.risk_level, risk_score: c.risk_score,
    fraud_flag: c.fraud_flag, assessor: userById(c.assessor_id)?.name ?? null, quotation_total: c.quotation?.total ?? null,
  };
}

// Approved claims by the same claimant in the 365 days before this incident (backend: workflow.recent_approved_claims)
function recentApproved(c) {
  const since = new Date(c.incident_date);
  since.setDate(since.getDate() - 365);
  const from = since.toISOString().slice(0, 10);
  return claims.filter((o) => o.id !== c.id && o.claimant_id === c.claimant_id && o.decision === 'approved'
                              && o.incident_date >= from && o.incident_date <= c.incident_date);
}

const inr = (n) => `₹${Number(n).toLocaleString('en-IN')}`;

// Same rule as the backend (workflow.payout_breakdown): 5% per recent approved claim, at most 20%
function payoutBreakdown(c) {
  if (!c.quotation) return null;
  const p = policyOf(c);
  const after = Math.max(0, c.quotation.total - p.deductible);
  const recent = recentApproved(c).length;
  const rate = Math.round(Math.min(recent * 0.05, 0.2) * 100) / 100;
  const deduction = Math.round(after * rate);
  const suggested = Math.max(0, Math.min(after - deduction, p.sum_insured));
  let text = `Quotation ${inr(c.quotation.total)} minus the ${inr(p.deductible)} deductible leaves ${inr(after)}. `;
  text += recent
    ? `The claimant had ${recent} approved claim${recent === 1 ? '' : 's'} in the last 12 months, so ${Math.round(rate * 100)}% (${inr(deduction)}) is taken off. `
    : 'No approved claims in the last 12 months, so nothing is taken off for claim history. ';
  if (after - deduction > p.sum_insured) text += `This is more than the sum insured, so it is capped at ${inr(p.sum_insured)}. `;
  text += `Suggested payout: ${inr(suggested)}.`;
  return { quotation_total: c.quotation.total, deductible: p.deductible, after_deductible: after,
           recent_approved_claims: recent, history_rate: rate, history_deduction: deduction,
           sum_insured: p.sum_insured, suggested_payout: suggested, explanation: text };
}

function staffView(c) {
  const claimant = userById(c.claimant_id);
  return {
    ...claimantView(c),
    status_label: STATUSES[c.status].staff,
    claimant: { id: claimant.id, name: claimant.name, email: claimant.email },
    vehicle: clone(vehicleOf(c)),
    info_request: c.info_request, decision_note: c.decision_note,
    risk_level: c.risk_level, risk_score: c.risk_score, fraud_flag: c.fraud_flag, reasons: clone(c.reasons),
    images: clone(c.images), assessor: c.assessor_id ? person(userById(c.assessor_id)) : null,
    quotation: clone(c.quotation),
    previous_claims: claims.filter((o) => o.id !== c.id && (o.claimant_id === c.claimant_id || o.vehicle_id === c.vehicle_id))
      .map((o) => ({ id: o.id, incident_date: o.incident_date, status: o.status, status_label: STATUSES[o.status].staff,
                     registration: vehicleOf(o).registration, same_vehicle: o.vehicle_id === c.vehicle_id, decision: o.decision,
                     approved_amount: o.approved_amount })),
    recent_approved_claims: recentApproved(c).map((o) => ({
      id: o.id, incident_date: o.incident_date, registration: vehicleOf(o).registration,
      approved_amount: o.approved_amount, status: o.status, status_label: STATUSES[o.status].staff })),
    history: clone(c.history),
    timeline: c.history.map((h) => ({ status: h.to, label: STATUSES[h.to].staff, at: h.at })),
  };
}

function insurerView(c) {
  const p = policyOf(c);
  const breakdown = payoutBreakdown(c);
  const { vehicles: _vehicles, user_id: _userId, ...policy } = p;
  return { ...staffView(c), policy: clone(policy), payout_breakdown: breakdown,
           suggested_payout: breakdown?.suggested_payout ?? null,
           policy_valid_on_incident_date: p.start_date <= c.incident_date && c.incident_date <= p.end_date };
}

// ------------------------------------------------------------------ endpoints

export async function login(email, password) {
  await delay();
  const user = users.find((u) => u.email === String(email).trim().toLowerCase());
  if (!user || !password) fail(401, 'Wrong email or password');
  return { token: `mock:${user.id}`, user: { id: user.id, name: user.name, role: user.role } };
}

export async function register(name, email, password) {
  await delay();
  const clean = String(email).trim().toLowerCase();
  if (!String(name).trim()) fail(422, 'name: enter your full name');
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(clean)) fail(422, 'email: enter a valid email address');
  if (String(password).length < 8) fail(422, 'password: use at least 8 characters');
  if (users.some((u) => u.email === clean)) fail(400, 'An account with this email already exists. Sign in instead.');
  const user = { id: Math.max(...users.map((u) => u.id)) + 1, email: clean, name: String(name).trim(), role: 'claimant' };
  users.push(user);
  return { token: `mock:${user.id}`, user: { id: user.id, name: user.name, role: user.role } };
}

export async function getMe() {
  await delay(100);
  return clone(me());
}

export async function getMyPolicies() {
  await delay();
  const user = as('claimant');
  return clone(policies.filter((p) => p.user_id === user.id).map(({ user_id: _u, ...p }) => p));
}

export async function createClaim(body) {
  await delay();
  const user = as('claimant');
  for (const f of ['vehicle_id', 'incident_date', 'incident_time', 'location', 'severity', 'description']) {
    if (!body[f]) fail(422, `${f}: Field required`);
  }
  const { vehicle, policy } = findVehicle(body.vehicle_id);
  if (!vehicle || policy.user_id !== user.id) fail(400, 'This vehicle is not on any of your policies');
  if (body.incident_date < policy.start_date || body.incident_date > policy.end_date) {
    fail(400, `Policy ${policy.policy_number} was not valid on ${body.incident_date} (valid ${policy.start_date} to ${policy.end_date})`);
  }
  const claim = makeClaim({ ...body, id: nextClaimId++, claimant_id: user.id, vehicle_id: vehicle.id,
                            created_at: nowIso(), status: null });
  move(claim, 'submitted', user, 'Claim submitted');
  claims.unshift(claim);
  return claimantView(claim);
}

export async function uploadImages(id, files, onProgress) {
  const user = as('claimant');
  const claim = findClaim(id);
  if (claim.claimant_id !== user.id) fail(403, "You don't have access to this");
  if (claim.status !== 'submitted') fail(409, "Photos can only be added while the claim is 'Submitted'.");
  const bad = files.find((f) => !/jpe?g$/i.test(f.type) && !/\.jpe?g$/i.test(f.name));
  if (bad) fail(400, `${bad.name} is not a JPEG photo`);
  for (let p = 0; p <= 100; p += 25) { onProgress?.(p); await delay(120); }
  const saved = files.map(() => ({ image_id: nextImageId++, url: PHOTO }));
  // pretend the photo checks finish a few seconds later, then routing assigns an assessor
  setTimeout(() => {
    claim.images = saved.map((s) => ({ ...s, risk_level: 'low', risk_score: 0.3,
      modules: moduleSet({ ela: 0.3, noise: 0.35, copy_move: 0, jpeg: 0.1, ai_detector_1: 0.02, ai_detector_2: 0.03 }) }));
    Object.assign(claim, { risk_level: 'low', risk_score: 0.3, fraud_flag: false, assessor_id: ASSESSOR });
    move(claim, 'photos_checked', null, `${saved.length} photo(s) checked`);
    move(claim, 'awaiting_assessment', null, 'Assigned to Suresh Babu');
  }, 4000);
  return saved;
}

export async function getMyClaims() {
  await delay();
  const user = as('claimant');
  return claims.filter((c) => c.claimant_id === user.id)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map((c) => { const { timeline: _t, ...rest } = claimantView(c); return rest; });
}

export async function getMyClaim(id) {
  await delay();
  const user = as('claimant');
  const claim = findClaim(id);
  if (claim.claimant_id !== user.id) fail(403, "You don't have access to this");
  return claimantView(claim);
}

export async function reply(id, note, files) {
  await delay();
  const user = as('claimant');
  const claim = findClaim(id);
  if (claim.claimant_id !== user.id) fail(403, "You don't have access to this");
  if (claim.status !== 'more_info_requested') fail(409, 'You can only reply when we have asked for more information');
  if (!note.trim() && !files.length) fail(422, 'note: write a reply or add photos');
  files.forEach(() => claim.images.push({ image_id: nextImageId++, url: PHOTO, risk_level: null, risk_score: null, modules: [] }));
  move(claim, 'under_review', user, note.trim() + (files.length ? ` (${files.length} photo(s) added)` : ''));
  return claimantView(claim);
}

export async function getAssessorClaims() {
  await delay();
  const user = as('assessor');
  return claims.filter((c) => c.assessor_id === user.id).sort((a, b) => b.created_at.localeCompare(a.created_at)).map(staffSummary);
}

export async function getAssessorClaim(id) {
  await delay();
  const user = as('assessor');
  const claim = findClaim(id);
  if (claim.assessor_id !== user.id) fail(403, "You don't have access to this");
  return staffView(claim);
}

export async function submitQuotation(id, items, note) {
  await delay();
  const user = as('assessor');
  const claim = findClaim(id);
  if (claim.assessor_id !== user.id) fail(403, "You don't have access to this");
  if (!items.length) fail(422, 'items: add at least one part or labour row');
  move(claim, 'assessed', user, note);
  const rows = items.map((i) => ({ ...i, amount: i.quantity * i.unit_price }));
  claim.quotation = { total: rows.reduce((s, i) => s + i.amount, 0), note, assessor: person(user), items: rows };
  return staffView(claim);
}

export async function getPriceList() {
  await delay(150);
  as('assessor', 'insurer');
  return clone(priceList);
}

const RISK_ORDER = { high: 0, medium: 1, low: 2 };

export async function getInsurerClaims({ status, risk }) {
  await delay();
  as('insurer');
  return claims
    .filter((c) => (!status || c.status === status) && (!risk || c.risk_level === risk))
    .sort((a, b) => (Number(b.fraud_flag) - Number(a.fraud_flag))
      || ((RISK_ORDER[a.risk_level] ?? 3) - (RISK_ORDER[b.risk_level] ?? 3))
      || b.created_at.localeCompare(a.created_at))
    .map(staffSummary);
}

export async function getInsurerClaim(id) {
  await delay();
  as('insurer');
  return insurerView(findClaim(id));
}

export async function startReview(id) {
  await delay();
  const user = as('insurer');
  const claim = findClaim(id);
  move(claim, 'under_review', user, 'Review started');
  return insurerView(claim);
}

export async function requestInfo(id, message) {
  await delay();
  const user = as('insurer');
  if (!message.trim()) fail(422, 'message: write what you need from the claimant');
  const claim = findClaim(id);
  move(claim, 'more_info_requested', user, message.trim());
  claim.info_request = message.trim();
  return insurerView(claim);
}

export async function submitDecision(id, { outcome, amount, note }) {
  await delay();
  const user = as('insurer');
  const claim = findClaim(id);
  if (outcome === 'approved' && !(amount > 0)) fail(422, 'amount: enter the approved amount in whole rupees');
  if (!['approved', 'rejected', 'further_review'].includes(outcome)) fail(422, 'outcome: must be approved, rejected or further_review');
  if (outcome !== 'approved' && !note.trim()) fail(422, 'note: a note is required to reject or send for further review');
  move(claim, 'decided', user, `${outcome}${note ? `: ${note}` : ''}`);
  Object.assign(claim, { decision: outcome, approved_amount: outcome === 'approved' ? amount : null, decision_note: note });
  return insurerView(claim);
}

export async function settle(id) {
  await delay();
  const user = as('insurer');
  const claim = findClaim(id);
  if (claim.status === 'decided' && claim.decision !== 'approved') fail(409, 'Only an approved claim can be marked as settled');
  move(claim, 'settled', user, claim.approved_amount ? `Paid ${claim.approved_amount}` : '');
  return insurerView(claim);
}
