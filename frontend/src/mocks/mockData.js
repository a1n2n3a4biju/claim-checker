// Mock data shaped exactly like M3's backend (backend/app/main.py).
// mockClaims assumes GET /claims also returns overall_risk, risk_score, description
// and reviewer_decision (requested from M3).

export const mockClaims = [
  { id: 1, claimant_name: 'Ravi Kumar',    incident_date: '2026-11-15', description: 'Rear bumper damaged while parked',            created_at: '2026-11-18T10:24:00', overall_risk: 'high',   risk_score: 0.81, reviewer_decision: null },
  { id: 2, claimant_name: 'Anita Menon',   incident_date: '2026-11-12', description: 'Scratches on driver-side door',               created_at: '2026-11-17T15:02:00', overall_risk: 'medium', risk_score: 0.47, reviewer_decision: null },
  { id: 3, claimant_name: 'Joseph Mathew', incident_date: '2026-11-10', description: 'Cracked front bumper after minor collision',  created_at: '2026-11-16T09:41:00', overall_risk: 'low',    risk_score: 0.14, reviewer_decision: null },
  { id: 4, claimant_name: 'Priya Nair',    incident_date: '2026-11-08', description: 'Dented hood after hailstorm',                 created_at: '2026-11-15T11:30:00', overall_risk: 'high',   risk_score: 0.76, reviewer_decision: 'escalated', reviewer_note: 'Cloned dent area on the hood', reviewer_name: 'Hobhav S Fuzele', decided_at: '2026-11-16T09:12:00+00:00' } ,
  { id: 5, claimant_name: 'Arjun Das',     incident_date: '2026-11-19', description: 'Broken side mirror',                          created_at: '2026-11-20T08:05:00', overall_risk: null,     risk_score: null, reviewer_decision: null },
];

const HEAT = '/mock/claim_photo.svg';

// One module result, in the contract shape: { module, score, flags, artifacts }
const mod = (module, score, flags = [], heatmap = true) =>
  ({ module, score, flags, artifacts: heatmap ? { heatmap_url: HEAT } : {} });

// The six results each photo gets: four forensic checks, two AI detectors
const modules = ([ela, noise, copyMove, jpeg, ai1, ai2], flags = {}) => [
  mod('ela', ela, flags.ela),
  mod('noise', noise, flags.noise),
  mod('copy_move', copyMove, flags.copy_move),
  mod('jpeg', jpeg, flags.jpeg),
  mod('ai_detector_1', ai1, flags.ai_detector_1, false),
  mod('ai_detector_2', ai2, flags.ai_detector_2, false),
];

const photo = (image_id, risk_score, mods, duplicate_of = null) =>
  ({ image_id, url: '/mock/claim_photo.jpg', duplicate_of, risk_score, modules: mods });

const result = (claimId, images, reasons = []) => {
  const c = mockClaims.find((x) => x.id === claimId);
  return {
    claim_id: c.id,
    claimant_name: c.claimant_name,
    incident_date: c.incident_date,
    status: c.overall_risk ? 'analyzed' : 'not_analyzed',
    overall_risk: c.overall_risk,
    risk_score: c.risk_score,
    reviewer_note: c.reviewer_note ?? null,
    reviewer_name: c.reviewer_name ?? null,
    decided_at: c.decided_at ?? null,
    reasons,
    reviewer_decision: c.reviewer_decision,
    images,
  };
};

export const mockResults = {
  1: result(1, [
    photo(11, 0.81, modules([0.72, 0.64, 0.12, 0.58, 0.34, 0.71], {
      ela: ['Unusual error level near the rear bumper'],
      jpeg: ['Part of the photo (lower right, about 12% of the detailed area) has a different compression history; possible pasted region'],
      ai_detector_2: ['AI detector rates this photo likely AI-generated'],
    })),
    photo(12, 0.22, modules([0.20, 0.18, 0.05, 0.10, 0.08, 0.12])),
  ], [
    'Unusual error level near the rear bumper',
    'Part of the photo (lower right, about 12% of the detailed area) has a different compression history; possible pasted region',
    'AI detector rates this photo likely AI-generated',
  ]),

  2: result(2, [
    photo(21, 0.47, modules([0.38, 0.55, 0.08, 0.30, 0.12, 0.18], {
      noise: ['Noise pattern differs near the door'],
    })),
  ], ['Noise pattern differs near the door']),

  3: result(3, [
    photo(31, 0.14, modules([0.10, 0.12, 0.05, 0.20, 0.04, 0.06])),
  ], []),

  4: result(4, [
    photo(41, 0.76, modules([0.55, 0.40, 0.81, 0.35, 0.10, 0.15], {
      copy_move: ['Two areas of the photo are near-identical copies; possible cloned damage'],
    })),
    photo(42, 0.76, modules([0.55, 0.40, 0.81, 0.35, 0.10, 0.15]), 41),
  ], [
    'Photo 42 is identical to an earlier upload (photo 41)',
    'Two areas of the photo are near-identical copies; possible cloned damage',
  ]),

  5: result(5, [
    photo(51, null, []),
  ], []),
};