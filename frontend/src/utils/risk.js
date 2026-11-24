// Mirrors LOW_THRESHOLD and HIGH_THRESHOLD in backend/app/main.py.
// Update both when M2's fusion thresholds (E5.3) are set.
export const LOW_THRESHOLD = 0.45;
export const HIGH_THRESHOLD = 0.688;

export const riskLevel = (score) => {
  if (score == null) return null;
  if (score < LOW_THRESHOLD) return 'low';
  return score < HIGH_THRESHOLD ? 'medium' : 'high';
};

// One line describing where a claim stands.
export function claimStatus({ overall_risk, reviewer_decision }) {
  if (reviewer_decision === 'approved') return 'Approved by reviewer';
  if (reviewer_decision === 'escalated') return 'Escalated to fraud team';
  if (!overall_risk) return 'Not analyzed yet';
  if (overall_risk === 'low') return 'Fast processing';
  return 'Waiting for review';
}