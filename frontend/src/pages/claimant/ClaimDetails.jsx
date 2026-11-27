import { useCallback, useState } from 'react';
import { Link as RouterLink, useLocation, useParams } from 'react-router-dom';
import { Alert, Box, Button, TextField, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { errorText, getMyClaim, replyToInfoRequest } from '../../api';
import PhotoPicker from '../../components/PhotoPicker';
import { ErrorBox, Facts, Loading, PageTitle, Section, StatusBadge, Timeline } from '../../components/shared';
import { capitalise, formatDate, money } from '../../utils/format';
import useLoad from '../../utils/useLoad';

// Claimants see friendlier words and never any risk scores, risk levels, heatmaps or reasons.
const OUTCOME_TEXT = {
  approved: 'Approved',
  rejected: 'Not approved',
  further_review: 'Needs further review',
};

// Shown only when the status is more_info_requested. Calls POST /claims/{id}/reply.
function ReplyForm({ claimId, onDone }) {
  const [note, setNote] = useState('');
  const [files, setFiles] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const send = async (e) => {
    e.preventDefault();
    if (!note.trim() && !files.length) {
      setError('Write a reply or add photos');
      return;
    }
    setBusy(true);
    setError('');
    try {
      onDone(await replyToInfoRequest(claimId, note.trim(), files));
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
      if (err?.status === 409) onDone(null);   // status changed meanwhile: reload the claim
    }
  };

  return (
    <Box component="form" onSubmit={send} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <TextField label="Your reply" multiline minRows={3} fullWidth value={note} onChange={(e) => setNote(e.target.value)}
                 disabled={busy} sx={{ mb: 2 }} />
      <PhotoPicker files={files} onChange={setFiles} onError={setError} label="Add more photos (optional)" />
      <Button type="submit" variant="contained" sx={{ mt: 2 }} disabled={busy}>{busy ? 'Sending…' : 'Send reply'}</Button>
    </Box>
  );
}

// Timeline, quotation total, outcome and approved amount; an info request, if any. Calls GET /me/claims/{id}.
export default function ClaimDetails() {
  const { id } = useParams();
  const { state } = useLocation();
  const { data: claim, error, loading, reload, setData } = useLoad(useCallback(() => getMyClaim(id), [id]));

  if (loading && !claim) return <Loading />;
  if (!claim) {
    return (
      <>
        <Button component={RouterLink} to="/my/claims" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }}>My claims</Button>
        <ErrorBox error={error} />
      </>
    );
  }

  return (
    <>
      <Button component={RouterLink} to="/my/claims" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }}>My claims</Button>
      <PageTitle title={`Claim #${claim.id}`} subtitle={`${claim.vehicle.registration} · ${claim.vehicle.make ?? ''} ${claim.vehicle.model ?? ''}`}
                 action={<StatusBadge status={claim.status} audience="claimant" />} />
      <ErrorBox error={error} />
      {state?.justSubmitted && claim.status === 'submitted' && (
        <Alert severity="success" sx={{ mb: 3 }}>
          Thank you. We've received your claim and photos. You can follow its progress on this page.
        </Alert>
      )}

      {claim.status === 'more_info_requested' && (
        <Section title="We need more information" sx={{ borderColor: 'warning.main' }}>
          {claim.info_request && (
            <Alert severity="warning" sx={{ mb: 2 }}>{claim.info_request}</Alert>
          )}
          <ReplyForm claimId={claim.id} onDone={(updated) => (updated ? setData(updated) : reload())} />
        </Section>
      )}

      {claim.decision && (
        <Section title="Decision">
          <Facts rows={[
            ['Outcome', OUTCOME_TEXT[claim.decision] ?? 'Decision made'],
            claim.decision === 'approved' && ['Approved amount', money(claim.approved_amount)],
            claim.status === 'settled' && ['Payment', 'Paid'],
          ]} />
        </Section>
      )}

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '3fr 2fr' }, alignItems: 'start' }}>
        <Section title="Claim details" sx={{ mb: 0 }}>
          <Facts rows={[
            ['Incident date', formatDate(claim.incident_date)],
            ['Time', claim.incident_time],
            ['Location', claim.location],
            ['Severity', capitalise(claim.severity)],
            ['Repair quotation', claim.quotation_total != null ? money(claim.quotation_total) : 'Not yet'],
          ]} />
          {claim.description && (
            <Typography sx={{ mt: 2 }}><Box component="span" sx={{ color: 'text.secondary' }}>What happened: </Box>{claim.description}</Typography>
          )}
        </Section>
        <Section title="Progress" sx={{ mb: 0 }}>
          <Timeline items={claim.timeline} audience="claimant" />
        </Section>
      </Box>
    </>
  );
}
