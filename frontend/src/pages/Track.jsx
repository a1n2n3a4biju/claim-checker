import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Alert, Box, Button, Paper, TextField, Typography } from '@mui/material';
import { getClaimStatus } from '../api/claims';
import { firmTeal, serif } from '../theme';

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
// step times arrive in UTC (ending +00:00); shown in local time
const formatWhen = (iso) =>
  new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

function Timeline({ steps }) {
  return (
    <Box component="ol" sx={{ listStyle: 'none', p: 0, m: 0 }}>
      {steps.map((s, i) => {
        const last = i === steps.length - 1;
        return (
          <Box component="li" key={s.step} sx={{ display: 'grid', gridTemplateColumns: '28px 1fr', columnGap: 1.5 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <Box
                aria-hidden="true"
                sx={{
                  width: 16, height: 16, borderRadius: '50%', mt: 0.5,
                  bgcolor: s.done ? firmTeal : 'background.paper',
                  border: 2, borderColor: s.done ? firmTeal : 'divider',
                }}
              />
              {!last && <Box sx={{ width: 2, flexGrow: 1, minHeight: 28, bgcolor: s.done ? firmTeal : 'divider', my: 0.5 }} />}
            </Box>
            <Box sx={{ pb: last ? 0 : 2.5 }}>
              <Typography sx={{ fontWeight: s.done ? 600 : 400, color: s.done ? 'text.primary' : 'text.secondary' }}>
                {s.step}
                <Box component="span" sx={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)' }}>
                  {s.done ? ', done' : ', not yet'}
                </Box>
              </Typography>
              {s.time && <Typography variant="body2" color="text.secondary">{formatWhen(s.time)}</Typography>}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}

export default function Track() {
  const [params, setParams] = useSearchParams();
  const [claimNo, setClaimNo] = useState(params.get('claim') ?? '');
  const [code, setCode] = useState(params.get('code') ?? '');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const look = useCallback(async (no, c) => {
    setBusy(true);
    setError('');
    setResult(null);
    try {
      setResult(await getClaimStatus(Number(no), c.trim()));
    } catch (e) {
      setError(e?.response ? (e.response.data?.detail ?? 'The status couldn\'t be loaded.') : "Can't reach the server. Please try again in a moment.");
    } finally {
      setBusy(false);
    }
  }, []);

  // arriving from the Claim received page with both values: look it up straight away
  useEffect(() => {
    const no = params.get('claim'), c = params.get('code');
    if (no && c) {
      look(no, c);
      setParams({}, { replace: true });   // don't leave the code in the address bar
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = (e) => {
    e.preventDefault();
    if (!/^\d+$/.test(claimNo.trim()) || !code.trim()) {
      setError('Enter your claim number (digits only) and your tracking code.');
      return;
    }
    setParams({});                     // keep the code out of the address bar and browser history
    look(claimNo.trim(), code);
  };

  return (
    <Box sx={{ maxWidth: 640, mx: 'auto' }}>
      <Typography variant="h4" component="h1">Check your claim's status</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Enter the claim number and tracking code you received when you submitted your claim.
      </Typography>

      <Paper component="form" noValidate onSubmit={submit} sx={{ p: { xs: 2.5, md: 3 }, mb: 3 }}>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '160px 1fr auto' }, gap: 2, alignItems: 'start' }}>
          <TextField label="Claim number" value={claimNo} onChange={(e) => setClaimNo(e.target.value)}
                     inputMode="numeric" disabled={busy} />
          <TextField label="Tracking code" placeholder="K7Q2-MX9P" value={code} onChange={(e) => setCode(e.target.value)}
                     disabled={busy} autoComplete="off" />
          <Button type="submit" variant="contained" size="large" disabled={busy} sx={{ height: 56 }}>
            {busy ? 'Checking…' : 'Check status'}
          </Button>
        </Box>
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </Paper>

      {result && (
        <Paper sx={{ p: { xs: 2.5, md: 4 } }}>
          <Typography color="text.secondary" sx={{ mb: 0.5 }}>
            Claim #{result.claim_id}, {result.claimant_name}, incident on {formatDate(result.incident_date)}
          </Typography>
          <Typography sx={{ fontFamily: serif, fontWeight: 700, fontSize: '1.75rem', lineHeight: 1.2 }}>{result.status}</Typography>
          <Typography sx={{ mb: 3 }}>{result.message}</Typography>
          <Timeline steps={result.steps} />
        </Paper>
      )}
    </Box>
  );
}
