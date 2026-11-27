import { Route, Routes, Link as RouterLink, useLocation } from 'react-router-dom';
import { Box, Button, Typography } from '@mui/material';
import { USE_MOCK } from './api';
import { HOME, useAuth } from './auth/AuthContext';
import RequireRole from './components/RequireRole';
import { firmTeal, ink, serif } from './theme';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/claimant/Dashboard';
import MyClaims from './pages/claimant/MyClaims';
import ClaimDetails from './pages/claimant/ClaimDetails';
import SubmitClaim from './pages/claimant/SubmitClaim';
import AssignedClaims from './pages/assessor/AssignedClaims';
import AssessorClaim from './pages/assessor/AssessorClaim';
import ClaimsQueue from './pages/insurer/ClaimsQueue';
import InsurerClaim from './pages/insurer/InsurerClaim';

const onDark = '#BFD9DE';        // light teal text on the ink header
const width = { maxWidth: 1180, mx: 'auto', px: { xs: 2, md: 4 } };

// Each role sees only its own pages in the menu
const NAV = {
  claimant: [['/my/claims', 'My claims'], ['/my/claims/new', 'Submit a claim'], ['/my/policies', 'My policies']],
  assessor: [['/assessor/claims', 'Assigned claims']],
  insurer: [['/insurer/claims', 'Claims queue']],
};
const ROLE_NAME = { claimant: 'Customer', assessor: 'Assessor', insurer: 'Insurance team' };

function Mark() {
  // A case file with a check: the ClaimProof mark
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
    <Button component={RouterLink} to={to} aria-current={active ? 'page' : undefined}
            sx={{ color: active ? '#fff' : onDark, borderRadius: 0, px: 0.5, minHeight: { md: 64 }, borderBottom: 3,
                  borderColor: active ? onDark : 'transparent', '&:hover': { color: '#fff', bgcolor: 'transparent' } }}>
      {label}
    </Button>
  );
}

function Header() {
  const { user, signOut } = useAuth();
  const { pathname } = useLocation();
  const links = user ? NAV[user.role] : [];
  // the most specific matching link is the active one
  const active = links.map(([to]) => to).filter((to) => pathname === to || pathname.startsWith(`${to}/`))
    .sort((a, b) => b.length - a.length)[0];

  return (
    <Box component="header" sx={{ bgcolor: ink, color: '#fff', '& :focus-visible': { outlineColor: onDark } }}>
      <Box sx={{ ...width, minHeight: 64, display: 'flex', alignItems: 'center', flexWrap: 'wrap', columnGap: { xs: 2, md: 4 }, rowGap: 1, py: { xs: 1.5, md: 0 } }}>
        <Box component={RouterLink} to={user ? HOME[user.role] : '/'} sx={{ display: 'flex', alignItems: 'center', gap: 1.25, color: '#fff', textDecoration: 'none' }}>
          <Mark />
          <Typography component="span" sx={{ fontFamily: serif, fontWeight: 700, fontSize: '1.3rem', letterSpacing: '-0.01em' }}>ClaimProof</Typography>
        </Box>
        <Box component="nav" aria-label="Main" sx={{ display: 'flex', gap: 3, alignSelf: 'stretch', alignItems: 'center', flexWrap: 'wrap' }}>
          {links.map(([to, label]) => <NavLink key={to} to={to} label={label} active={to === active} />)}
        </Box>
        <Box sx={{ flexGrow: 1 }} />
        {!user && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Button size="small" component={RouterLink} to="/login" sx={{ color: onDark, '&:hover': { color: '#fff' } }}>Sign in</Button>
            <Button size="small" variant="outlined" component={RouterLink} to="/register"
                    sx={{ color: '#fff', borderColor: 'rgba(255,255,255,0.5)', '&:hover': { borderColor: '#fff' } }}>
              Create account
            </Button>
          </Box>
        )}
        {user && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Typography variant="body2" sx={{ color: onDark }}>
              <Box component="span" sx={{ color: '#fff', fontWeight: 600 }}>{user.name}</Box> · {ROLE_NAME[user.role]}
            </Typography>
            <Button size="small" variant="outlined" onClick={signOut}
                    sx={{ color: '#fff', borderColor: 'rgba(255,255,255,0.5)', '&:hover': { borderColor: '#fff' } }}>
              Sign out
            </Button>
          </Box>
        )}
      </Box>
    </Box>
  );
}

function NotFound() {
  return (
    <Box sx={{ textAlign: 'center', mt: 6 }}>
      <Typography variant="h5" component="h1" sx={{ mb: 2 }}>Not found</Typography>
      <Button variant="contained" component={RouterLink} to="/">Go to my home page</Button>
    </Box>
  );
}

const claimant = (el) => <RequireRole role="claimant">{el}</RequireRole>;
const assessor = (el) => <RequireRole role="assessor">{el}</RequireRole>;
const insurer = (el) => <RequireRole role="insurer">{el}</RequireRole>;

export default function App() {
  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header />
      {USE_MOCK && (
        <Box sx={{ bgcolor: '#FBF1DE', borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="body2" sx={{ ...width, py: 0.75 }}>
            Showing sample data (mock mode). Set VITE_USE_MOCK=false in frontend/.env.local to use the backend.
          </Typography>
        </Box>
      )}
      <Box component="main" sx={{ ...width, width: '100%', boxSizing: 'border-box', flexGrow: 1, py: { xs: 3, md: 5 } }}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route path="/my/claims" element={claimant(<MyClaims />)} />
          <Route path="/my/claims/new" element={claimant(<SubmitClaim />)} />
          <Route path="/my/claims/:id" element={claimant(<ClaimDetails />)} />
          <Route path="/my/policies" element={claimant(<Dashboard />)} />

          <Route path="/assessor/claims" element={assessor(<AssignedClaims />)} />
          <Route path="/assessor/claims/:id" element={assessor(<AssessorClaim />)} />

          <Route path="/insurer/claims" element={insurer(<ClaimsQueue />)} />
          <Route path="/insurer/claims/:id" element={insurer(<InsurerClaim />)} />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </Box>
      <Box component="footer" sx={{ borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
        <Typography variant="body2" color="text.secondary" sx={{ ...width, py: 2.5 }}>
          ClaimProof. Photo checks flag risk; people make every decision.
        </Typography>
      </Box>
    </Box>
  );
}
