import { Routes, Route, Navigate, Link as RouterLink, useLocation } from 'react-router-dom';
import { Box, Button, Typography } from '@mui/material';
import ClaimsList from './pages/ClaimsList';
import NewClaim from './pages/NewClaim';
import Results from './pages/Results';
import SignInDialog from './components/SignInDialog';
import { USE_MOCK } from './api/claims';
import { useAuth } from './auth/AuthContext';
import { firmTeal, ink, serif } from './theme';

const onDark = '#BFD9DE';        // light teal text on the ink header
const width = { maxWidth: 1180, mx: 'auto', px: { xs: 2, md: 4 } };

function Mark() {
  // A case file with a check: the firm's mark
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">
      <rect width="30" height="30" rx="6" fill={firmTeal} />
      <path d="M10 7.5h7.5l4 4v11h-11.5z" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M17.5 7.5v4h4" fill="none" stroke="#fff" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M12.8 17l2.2 2.2 3.8-4.4" fill="none" stroke={onDark} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function NavLink({ to, label, active }) {
  return (
    <Button
      component={RouterLink}
      to={to}
      aria-current={active ? 'page' : undefined}
      sx={{
        color: active ? '#fff' : onDark,
        borderRadius: 0,
        px: 0.5,
        minHeight: { md: 64 },
        borderBottom: 3,
        borderColor: active ? onDark : 'transparent',
        '&:hover': { color: '#fff', bgcolor: 'transparent' },
      }}
    >
      {label}
    </Button>
  );
}

function ReviewerStatus() {
  const { session, openSignIn, signOut } = useAuth();
  if (!session) {
    return (
      <Button
        variant="outlined"
        size="small"
        onClick={openSignIn}
        sx={{ color: '#fff', borderColor: 'rgba(255,255,255,0.5)', '&:hover': { borderColor: '#fff' } }}
      >
        Reviewer sign-in
      </Button>
    );
  }
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      <Typography variant="body2" sx={{ color: onDark }}>
        Signed in as <Box component="span" sx={{ color: '#fff', fontWeight: 600 }}>{session.name}</Box>
      </Typography>
      <Button size="small" onClick={signOut} sx={{ color: onDark, '&:hover': { color: '#fff' } }}>Sign out</Button>
    </Box>
  );
}

export default function App() {
  const { pathname } = useLocation();
  const inQueue = pathname === '/claims' || /^\/claims\/\d+/.test(pathname);

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Box component="header" sx={{ bgcolor: ink, color: '#fff', '& :focus-visible': { outlineColor: onDark } }}>
        <Box
          sx={{
            ...width,
            minHeight: 64,
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            columnGap: { xs: 2, md: 4 },
            rowGap: 1,
            py: { xs: 1.5, md: 0 },
          }}
        >
          <Box component={RouterLink} to="/claims" sx={{ display: 'flex', alignItems: 'center', gap: 1.25, color: '#fff', textDecoration: 'none' }}>
            <Mark />
            <Typography component="span" sx={{ fontFamily: serif, fontWeight: 700, fontSize: '1.3rem', letterSpacing: '-0.01em' }}>
              Claim Checker
            </Typography>
          </Box>

          <Box component="nav" aria-label="Main" sx={{ display: 'flex', gap: 3, alignSelf: 'stretch', alignItems: 'center' }}>
            <NavLink to="/claims" label="Review queue" active={inQueue} />
            <NavLink to="/claims/new" label="New claim" active={pathname === '/claims/new'} />
          </Box>

          <Box sx={{ flexGrow: 1 }} />
          <ReviewerStatus />
        </Box>
      </Box>

      {USE_MOCK && (
        <Box sx={{ bgcolor: '#FBF1DE', borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="body2" sx={{ ...width, py: 0.75 }}>
            Showing sample data. Set VITE_USE_MOCK=false in frontend/.env.local to use the backend.
          </Typography>
        </Box>
      )}

      <Box component="main" sx={{ ...width, width: '100%', boxSizing: 'border-box', flexGrow: 1, py: { xs: 3, md: 5 } }}>
        <Routes>
          <Route path="/" element={<Navigate to="/claims" replace />} />
          <Route path="/claims" element={<ClaimsList />} />
          <Route path="/claims/new" element={<NewClaim />} />
          <Route path="/claims/:id" element={<Results />} />
        </Routes>
      </Box>

      <Box component="footer" sx={{ borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
        <Typography variant="body2" color="text.secondary" sx={{ ...width, py: 2.5 }}>
          Every flagged claim is reviewed by a person. The tool never rejects a claim on its own.
        </Typography>
      </Box>

      <SignInDialog />
    </Box>
  );
}
