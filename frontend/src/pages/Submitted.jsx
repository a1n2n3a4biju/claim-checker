import { useState } from 'react';
import { Link as RouterLink, useLocation, useParams } from 'react-router-dom';
import { Alert, Box, Button, Paper, Typography } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlined';
import { firmTeal } from '../theme';

// Shown once, right after a claim is submitted. The tracking code arrives only here (from the submit response).
export default function Submitted() {
  const { id } = useParams();
  const { state } = useLocation();
  const code = state?.trackingCode;
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Paper sx={{ maxWidth: 640, mx: 'auto', p: { xs: 3, md: 5 } }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
        <CheckCircleOutlineIcon sx={{ color: firmTeal, fontSize: 32 }} />
        <Typography variant="h4" component="h1">Claim received</Typography>
      </Box>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        {state?.name ? `Thank you, ${state.name}. ` : ''}
        Your claim number is <strong>#{id}</strong>
        {state?.photos ? `, with ${state.photos} ${state.photos === 1 ? 'photo' : 'photos'}.` : '.'}
      </Typography>

      {code ? (
        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 2.5, mb: 3, bgcolor: 'background.default' }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Your tracking code</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Typography sx={{ fontSize: '1.75rem', fontWeight: 700, letterSpacing: '0.08em', fontVariantNumeric: 'tabular-nums' }}>
              {code}
            </Typography>
            <Button variant="outlined" size="small" onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
          </Box>
          <Typography variant="body2" sx={{ mt: 1.5 }}>
            Keep this code. You'll need it with your claim number to check your claim's status, and it can't be shown again.
          </Typography>
        </Box>
      ) : (
        <Alert severity="info" sx={{ mb: 3 }}>
          The tracking code is shown only once, right after submitting. If you didn't save it, contact us with your claim number.
        </Alert>
      )}

      <Typography sx={{ fontWeight: 600, mb: 1 }}>What happens next</Typography>
      <Box component="ol" sx={{ m: 0, pl: 2.5, mb: 4 }}>
        <li><Typography>Your photos are checked for signs of editing and AI generation.</Typography></li>
        <li><Typography>A reviewer looks at your claim if anything needs a closer look.</Typography></li>
        <li><Typography>You'll be contacted about the outcome. You can check the status at any time.</Typography></li>
      </Box>

      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
        {code && (
          <Button variant="contained" component={RouterLink} to={`/track?claim=${id}&code=${encodeURIComponent(code)}`}>
            Check status
          </Button>
        )}
        <Button variant="outlined" component={RouterLink} to="/claims/new">Submit another claim</Button>
        <Button component={RouterLink} to="/">Back to home</Button>
      </Box>
    </Paper>
  );
}
