// Mock data shaped like the backend API in the Epic Plan.
// Confirm field names with M3; update here if the real API differs.

export const mockClaims = [
  { id: 1, claimant_name: 'Ravi Kumar',    incident_date: '2026-11-15', description: 'Rear bumper damaged while parked',           created_at: '2026-11-18T10:24:00', overall_risk: 'high',   risk_score: 0.81, status: 'pending_review' },
  { id: 2, claimant_name: 'Anita Menon',   incident_date: '2026-11-12', description: 'Scratches on driver-side door',              created_at: '2026-11-17T15:02:00', overall_risk: 'medium', risk_score: 0.47, status: 'pending_review' },
  { id: 3, claimant_name: 'Joseph Mathew', incident_date: '2026-11-10', description: 'Cracked front bumper after minor collision', created_at: '2026-11-16T09:41:00', overall_risk: 'low',    risk_score: 0.14, status: 'approved' },
];

// One module result follows the frozen contract: { module, score, flags, artifacts }
const mod = (module, score, flags = [], artifacts = {}) => ({ module, score, flags, artifacts });

const makeResult = (claimId, risk, score, reasons, modules) => ({
  claim_id: claimId,
  overall_risk: risk,          // 'low' | 'medium' | 'high'
  risk_score: score,           // fusion output, 0-1
  reasons,
  status: mockClaims.find((c) => c.id === claimId)?.status ?? 'pending_review',
  images: [
    {
      image_id: claimId * 10 + 1,
      file_url: '/mock/claim_photo.jpg',
      risk_level: risk,
      risk_score: score,
      modules,
    },
  ],
});

export const mockResults = {
  1: makeResult(1, 'high', 0.81,
    ['Possible edited region near the rear bumper', 'AI detector rates this image likely AI-generated'],
    [
      mod('ela', 0.72, ['Unusual error level near the rear bumper'], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('noise', 0.64, ['Noise pattern differs in one region'], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('copy_move', 0.12, [], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('jpeg', 0.58, ['Signs this image was saved twice at different quality levels'], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('ai_det1', 0.34),
      mod('ai_det2', 0.71, ['AI detector rates this image likely AI-generated']),
    ]),
  2: makeResult(2, 'medium', 0.47,
    ['Noise pattern differs near the door'],
    [
      mod('ela', 0.38, [], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('noise', 0.55, ['Noise pattern differs near the door'], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('copy_move', 0.08, [], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('jpeg', 0.30, [], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('ai_det1', 0.12),
      mod('ai_det2', 0.18),
    ]),
  3: makeResult(3, 'low', 0.14,
    ['No strong signs of editing or AI generation'],
    [
      mod('ela', 0.10, [], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('noise', 0.12, [], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('copy_move', 0.05, [], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('jpeg', 0.20, [], { heatmap_url: '/mock/claim_photo.jpg' }),
      mod('ai_det1', 0.04),
      mod('ai_det2', 0.06),
    ]),
};