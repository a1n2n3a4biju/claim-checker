import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Box, Button, Paper, Typography } from '@mui/material';
import CoverArt from '../components/CoverArt';
import { useAuth } from '../auth/AuthContext';
import { firmTeal, serif } from '../theme';

const steps = [
  { title: 'You submit', text: 'Tell us what happened and add photos of the damage. You get a claim number and a tracking code.' },
  { title: 'Each photo is checked', text: 'Every photo is checked for signs of editing and of AI generation.' },
  { title: 'A reviewer decides', text: 'A person looks at what the checks found and makes the call. No claim is rejected automatically.' },
];

function Choice({ title, audience, text, action }) {
  return (
    <Paper sx={{ p: { xs: 3, md: 4 }, display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Typography variant="h5" component="h2">{title}</Typography>
      <Typography variant="body2" sx={{ color: firmTeal, fontWeight: 600 }}>{audience}</Typography>
      <Typography color="text.secondary" sx={{ flexGrow: 1, mb: 2 }}>{text}</Typography>
      <Box>{action}</Box>
    </Paper>
  );
}

export default function Landing() {
  const { session, openSignIn } = useAuth();
  const navigate = useNavigate();

  const review = () => (session ? navigate('/claims') : openSignIn('/claims'));

  return (
    <>
      {/* hero */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.05fr 1fr' }, gap: { xs: 4, md: 6 }, alignItems: 'center', mb: { xs: 5, md: 7 } }}>
        <Box>
          <Typography component="h1" sx={{ fontFamily: serif, fontWeight: 700, fontSize: { xs: '2.25rem', md: '3rem' }, lineHeight: 1.1, letterSpacing: '-0.015em', mb: 2 }}>
            Welcome to ClaimProof
          </Typography>
          <Typography sx={{ fontSize: { xs: '1.125rem', md: '1.25rem' }, lineHeight: 1.45, mb: 2 }}>
            Every claim photo is checked for editing and AI generation before a person decides.
          </Typography>
          <Typography color="text.secondary" sx={{ maxWidth: 520 }}>
            Submit your claim in a few minutes. Our reviewers see what the checks found and make the final call;
            no claim is rejected automatically.
          </Typography>
        </Box>
        <Box sx={{ maxWidth: 520, width: '100%', justifySelf: 'center' }}>
          <CoverArt />
        </Box>
      </Box>

      {/* the two ways in */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3, mb: 2 }}>
        <Choice
          title="Submit a claim"
          audience="For policyholders"
          text="Upload photos of the damage and tell us what happened. No account needed."
          action={<Button variant="contained" size="large" component={RouterLink} to="/claims/new">Start a claim</Button>}
        />
        <Choice
          title="Review claims"
          audience="For adjusters and the fraud team"
          text="See each claim's risk and the evidence behind it, and record your decision."
          action={<Button variant="outlined" size="large" onClick={review}>{session ? 'Go to review queue' : 'Sign in to review'}</Button>}
        />
      </Box>
      <Typography color="text.secondary" sx={{ mb: { xs: 6, md: 8 } }}>
        Already submitted a claim?{' '}
        <Box component={RouterLink} to="/track" sx={{ color: 'primary.main', fontWeight: 600 }}>Check its status</Box>
      </Typography>

      {/* how it works: a real sequence, so the steps are numbered */}
      <Typography variant="h5" component="h2" sx={{ mb: 3 }}>How it works</Typography>
      <Box component="ol" sx={{ listStyle: 'none', p: 0, m: 0, display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' }, gap: { xs: 3, md: 4 } }}>
        {steps.map((s, i) => (
          <Box component="li" key={s.title} sx={{ borderTop: 2, borderColor: 'divider', pt: 2 }}>
            <Typography sx={{ fontFamily: serif, fontWeight: 700, fontSize: '1.75rem', lineHeight: 1, color: firmTeal, mb: 1 }}>{i + 1}</Typography>
            <Typography sx={{ fontWeight: 600, mb: 0.5 }}>{s.title}</Typography>
            <Typography color="text.secondary">{s.text}</Typography>
          </Box>
        ))}
      </Box>
    </>
  );
}
