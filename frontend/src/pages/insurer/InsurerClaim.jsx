import { useCallback } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { Alert, Box, Button, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { getInsurerClaim } from '../../api';
import { ClaimFacts, PhotoEvidence, PreviousClaims, QuotationTable, RiskSummary } from '../../components/StaffClaim';
import { ErrorBox, Facts, Loading, PageTitle, Section, StatusBadge, Timeline } from '../../components/shared';
import { formatDate, money } from '../../utils/format';
import { OUTCOMES } from '../../utils/status';
import useLoad from '../../utils/useLoad';
import ClaimActions from './ClaimActions';

// How the suggested payout is worked out (payout_breakdown from the backend). Only a suggestion.
function PayoutBreakdown({ breakdown: b }) {
  if (!b) return <Typography color="text.secondary">No quotation yet, so there is no suggested payout.</Typography>;
  const row = (label, value, opts = {}) => (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, py: 0.75,
               borderTop: opts.total ? 2 : 0, borderColor: 'divider', fontWeight: opts.total ? 700 : 400 }}>
      <Typography component="span" sx={{ fontWeight: 'inherit', color: opts.muted ? 'text.secondary' : 'text.primary' }}>{label}</Typography>
      <Typography component="span" sx={{ fontWeight: 'inherit', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{value}</Typography>
    </Box>
  );
  const pct = Math.round(b.history_rate * 100);
  return (
    <Box>
      {row('Quotation total', money(b.quotation_total))}
      {row('Deductible', `− ${money(b.deductible)}`)}
      {row('After deductible', money(b.after_deductible), { muted: true })}
      {row(`Claim history: ${b.recent_approved_claims} approved in 12 months (${pct}%)`,
           b.history_deduction ? `− ${money(b.history_deduction)}` : money(0))}
      {row('Suggested payout', money(b.suggested_payout), { total: true })}
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>{b.explanation}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        Capped at the sum insured ({money(b.sum_insured)}). It is only a suggestion: you decide the final amount.
      </Typography>
    </Box>
  );
}

// Everything: claimant, policy, premium, dates, vehicle and claim history, photo checks and reasons,
// the quotation, suggested payout, full history, and the actions. Calls GET /insurer/claims/{id}.
export default function InsurerClaim() {
  const { id } = useParams();
  const { data: claim, error, loading, reload, setData } = useLoad(useCallback(() => getInsurerClaim(id), [id]));

  const back = <Button component={RouterLink} to="/insurer/claims" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }}>Claims queue</Button>;
  if (loading && !claim) return <Loading />;
  if (!claim) return <>{back}<ErrorBox error={error} /></>;
  const p = claim.policy;

  return (
    <>
      {back}
      <PageTitle title={`Claim #${claim.id}`} subtitle={`${claim.claimant.name} · ${claim.vehicle.registration}`}
                 action={<StatusBadge status={claim.status} />} />
      <ErrorBox error={error} />
      {!claim.policy_valid_on_incident_date && (
        <Alert severity="error" sx={{ mb: 3 }}>The policy was not valid on the incident date.</Alert>
      )}

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '3fr 2fr' }, alignItems: 'start' }}>
        <Box sx={{ minWidth: 0 }}>
          <RiskSummary claim={claim} />
          <PhotoEvidence images={claim.images} />
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Section title="Actions" sx={{ borderColor: 'primary.main' }}>
            {/* key resets the forms when the status changes */}
            <ClaimActions key={claim.status} claim={claim} onUpdated={setData} onConflict={reload} />
          </Section>
          <Section title="Payout">
            <PayoutBreakdown breakdown={claim.payout_breakdown} />
            {claim.decision && (
              <Box sx={{ mt: 2 }}>
                <Facts rows={[
                  ['Decision', OUTCOMES[claim.decision] ?? claim.decision],
                  claim.decision === 'approved' && ['Approved amount', money(claim.approved_amount)],
                  claim.decision_note && ['Decision note', claim.decision_note],
                ]} />
              </Box>
            )}
          </Section>
        </Box>
      </Box>

      <Section title={`Policy ${p.policy_number}`}>
        <Facts rows={[
          ['Valid', `${formatDate(p.start_date)} to ${formatDate(p.end_date)}`],
          ['Valid on incident date', claim.policy_valid_on_incident_date ? 'Yes' : 'No'],
          ['Premium', money(p.premium)],
          ['Deductible', money(p.deductible)],
          ['Sum insured', money(p.sum_insured)],
        ]} />
      </Section>
      <ClaimFacts claim={claim} />
      <Section title="Quotation">
        {claim.quotation ? <QuotationTable quotation={claim.quotation} /> : <Typography color="text.secondary">No quotation yet.</Typography>}
      </Section>
      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, alignItems: 'start' }}>
        <PreviousClaims claims={claim.previous_claims} recent={claim.recent_approved_claims} linkBase="/insurer/claims" />
        <Section title="Full history"><Timeline items={claim.history} /></Section>
      </Box>
    </>
  );
}
