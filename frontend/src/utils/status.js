// Contract section 2.2: claim statuses. Copy of the backend's table; keys are used in code.
export const STATUSES = {
  submitted:           { staff: 'Submitted',            claimant: 'Received' },
  photos_checked:      { staff: 'Photos checked',       claimant: 'Received' },
  awaiting_assessment: { staff: 'Awaiting assessment',  claimant: 'Being assessed' },
  assessed:            { staff: 'Assessed',             claimant: 'Being assessed' },
  under_review:        { staff: 'Under insurer review', claimant: 'Under review' },
  more_info_requested: { staff: 'More info requested',  claimant: 'We need more information' },
  decided:             { staff: 'Decided',              claimant: 'Decision made' },
  settled:             { staff: 'Settled',              claimant: 'Settled' },
};

export const STATUS_KEYS = Object.keys(STATUSES);

export const statusLabel = (status, audience = 'staff') => STATUSES[status]?.[audience] ?? status;

// Contract section 2.4
export const OUTCOMES = {
  approved: 'Approved',
  rejected: 'Rejected',
  further_review: 'Further review',
};

export const SEVERITIES = ['minor', 'moderate', 'severe'];
