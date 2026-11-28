// Mirrors the fusion model thresholds (0.45 / 0.688), unchanged from v1.
export const LOW_THRESHOLD = 0.45;
export const HIGH_THRESHOLD = 0.688;

export const riskLevel = (score) => {
  if (score == null) return null;
  if (score < LOW_THRESHOLD) return 'low';
  return score < HIGH_THRESHOLD ? 'medium' : 'high';
};
