import { useState } from 'react';
import { Alert, Box, Button, TextField, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { errorText, requestInfo, settleClaim, startReview, submitDecision } from '../../api';
import { money } from '../../utils/format';
import { OUTCOMES } from '../../utils/status';

// Only the buttons allowed for the current status (contract 2.3). If the backend still answers 409,
// show its message and reload the claim.
export default function ClaimActions({ claim, onUpdated, onConflict }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  const [outcome, setOutcome] = useState('approved');
  const [amount, setAmount] = useState(claim.suggested_payout ?? '');
  const [note, setNote] = useState('');

  const run = async (action) => {
    setBusy(true);
    setError('');
    try {
      onUpdated(await action());
    } catch (err) {
      setError(errorText(err));
      if (err?.status === 409) onConflict();
    } finally {
      setBusy(false);
    }
  };

  const decide = (e) => {
    e.preventDefault();
    if (outcome === 'approved' && !(Number(amount) > 0 && Number.isInteger(Number(amount)))) {
      setError('Enter the approved amount in whole rupees');
      return;
    }
    if (outcome !== 'approved' && !note.trim()) {
      setError('A note is required to reject or send for further review');
      return;
    }
    run(() => submitDecision(claim.id, outcome, Number(amount), note.trim()));
  };

  const askInfo = (e) => {
    e.preventDefault();
    if (!infoMessage.trim()) {
      setError('Write what you need from the claimant');
      return;
    }
    run(() => requestInfo(claim.id, infoMessage.trim()));
  };

  const errorBox = error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>;

  switch (claim.status) {
    case 'assessed':
      return (
        <>
          {errorBox}
          <Typography sx={{ mb: 2 }}>The assessor's quotation is in. Start the review to decide on this claim.</Typography>
          <Button variant="contained" onClick={() => run(() => startReview(claim.id))} disabled={busy}>Start review</Button>
        </>
      );

    case 'under_review':
      return (
        <>
          {errorBox}
          <Box component="form" onSubmit={decide} noValidate sx={{ mb: 4 }}>
            <Typography sx={{ fontWeight: 600, mb: 1 }}>Decide</Typography>
            <ToggleButtonGroup exclusive value={outcome} onChange={(_, v) => v && setOutcome(v)} size="small" sx={{ mb: 2, flexWrap: 'wrap' }}>
              <ToggleButton value="approved">Approve</ToggleButton>
              <ToggleButton value="rejected">Reject</ToggleButton>
              <ToggleButton value="further_review">Further review</ToggleButton>
            </ToggleButtonGroup>
            {outcome === 'approved' && (
              <TextField label="Approved amount (₹)" type="number" value={amount} onChange={(e) => setAmount(e.target.value)}
                         disabled={busy} sx={{ display: 'block', mb: 2 }} slotProps={{ htmlInput: { min: 1, step: 1 } }}
                         helperText={claim.suggested_payout != null
                           ? `Pre-filled with the suggested payout ${money(claim.suggested_payout)} (see Payout below). You decide the final amount.`
                           : 'No quotation, so there is no suggested payout'} />
            )}
            <TextField label={outcome === 'approved' ? 'Note (optional)' : 'Note (required)'} multiline minRows={2} fullWidth
                       value={note} onChange={(e) => setNote(e.target.value)} disabled={busy} sx={{ mb: 2 }} />
            <Button type="submit" variant="contained" disabled={busy}
                    color={outcome === 'approved' ? 'primary' : 'error'}>
              {outcome === 'approved' ? `Approve ${amount ? money(Number(amount)) : ''}` : outcome === 'rejected' ? 'Reject claim' : 'Send for further review'}
            </Button>
          </Box>

          <Box component="form" onSubmit={askInfo} noValidate>
            <Typography sx={{ fontWeight: 600, mb: 1 }}>Ask for more info</Typography>
            <TextField label="Message to the claimant" multiline minRows={2} fullWidth value={infoMessage}
                       onChange={(e) => setInfoMessage(e.target.value)} disabled={busy} sx={{ mb: 2 }} />
            <Button type="submit" variant="outlined" disabled={busy}>Ask for more info</Button>
          </Box>
        </>
      );

    case 'decided':
      return (
        <>
          {errorBox}
          {claim.decision === 'approved' ? (
            <>
              <Typography sx={{ mb: 2 }}>Approved for {money(claim.approved_amount)}. Mark it settled once it has been paid.</Typography>
              <Button variant="contained" onClick={() => run(() => settleClaim(claim.id))} disabled={busy}>Mark settled</Button>
            </>
          ) : (
            <Typography>Decision: {OUTCOMES[claim.decision]}. No further action.</Typography>
          )}
        </>
      );

    case 'more_info_requested':
      return <Typography>Waiting for the claimant to reply to: “{claim.info_request}”</Typography>;
    case 'settled':
      return <Typography>Settled: {money(claim.approved_amount)} paid.</Typography>;
    default:
      return <Typography>Waiting for the photo checks and the assessor's quotation. No action yet.</Typography>;
  }
}
