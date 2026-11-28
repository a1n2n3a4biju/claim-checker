import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { Alert, Box, Button } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { getAssessorClaim } from '../../api';
import { ClaimFacts, PhotoEvidence, PreviousClaims, QuotationTable, RiskSummary } from '../../components/StaffClaim';
import { ErrorBox, Loading, PageTitle, Section, StatusBadge, Timeline } from '../../components/shared';
import useLoad from '../../utils/useLoad';
import QuotationForm from './QuotationForm';

// Claim and incident details, vehicle and claimant history, photos with heatmaps, risk level, reasons,
// and the quotation form. Calls GET /assessor/claims/{id}.
export default function AssessorClaim() {
  const { id } = useParams();
  const { data: claim, error, loading, reload, setData } = useLoad(useCallback(() => getAssessorClaim(id), [id]));
  const [message, setMessage] = useState('');

  const back = <Button component={RouterLink} to="/assessor/claims" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }}>Assigned claims</Button>;
  if (loading && !claim) return <Loading />;
  if (!claim) return <>{back}<ErrorBox error={error} /></>;

  return (
    <>
      {back}
      <PageTitle title={`Claim #${claim.id}`} subtitle={`${claim.claimant.name} · ${claim.vehicle.registration}`}
                 action={<StatusBadge status={claim.status} />} />
      <ErrorBox error={error} />
      {message && <Alert severity="success" sx={{ mb: 3 }} onClose={() => setMessage('')}>{message}</Alert>}

      <RiskSummary claim={claim} />
      <PhotoEvidence images={claim.images} />
      <ClaimFacts claim={claim} />

      <Section title="Quotation">
        {claim.quotation ? (
          <QuotationTable quotation={claim.quotation} />
        ) : claim.status === 'awaiting_assessment' ? (
          <QuotationForm claimId={claim.id} onConflict={reload}
                         onSubmitted={(updated) => { setData(updated); setMessage('Quotation submitted. The claim is now assessed.'); }} />
        ) : (
          <Alert severity="info">A quotation can only be written while the claim is awaiting assessment.</Alert>
        )}
      </Section>

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, alignItems: 'start' }}>
        <PreviousClaims claims={claim.previous_claims} recent={claim.recent_approved_claims} />
        <Section title="History"><Timeline items={claim.history} /></Section>
      </Box>
    </>
  );
}
