import { Link as RouterLink, useLocation } from 'react-router-dom';
import { Alert, Box, Button, Paper, Typography } from '@mui/material';
import { useAuth } from '../auth/AuthContext';

// Reviewer-only pages: the review queue and claim evidence. Claimants see a sign-in prompt instead.
export default function RequireReviewer({ children }) {
  const { session, notice, openSignIn } = useAuth();
  const { pathname, search } = useLocation();

  if (session) return children;

  return (
    <Paper sx={{ maxWidth: 560, mx: 'auto', mt: { xs: 2, md: 6 }, p: { xs: 3, md: 5 }, textAlign: 'center' }}>
      <Typography variant="h4" component="h1" sx={{ mb: 1 }}>Reviewer sign-in required</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        The review queue and claim evidence are only for adjusters and the fraud team.
      </Typography>
      {notice && <Alert severity="warning" sx={{ mb: 3, textAlign: 'left' }}>{notice}</Alert>}
      <Box sx={{ display: 'flex', gap: 1.5, justifyContent: 'center', flexWrap: 'wrap' }}>
        <Button variant="contained" onClick={() => openSignIn(pathname + search)}>Sign in as reviewer</Button>
        <Button component={RouterLink} to="/">Back to home</Button>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 4 }}>
        Submitted a claim? <Box component={RouterLink} to="/track" sx={{ color: 'primary.main', fontWeight: 600 }}>Check its status</Box> with your claim number and tracking code.
      </Typography>
    </Paper>
  );
}
