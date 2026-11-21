import { Routes, Route, Navigate, Link as RouterLink, useLocation } from 'react-router-dom';
import { Box, Button, Typography } from '@mui/material';
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined';
import InboxOutlinedIcon from '@mui/icons-material/InboxOutlined';
import AddPhotoAlternateOutlinedIcon from '@mui/icons-material/AddPhotoAlternateOutlined';
import ClaimsList from './pages/ClaimsList';
import NewClaim from './pages/NewClaim';
import Results from './pages/Results';
import { USE_MOCK } from './api/claims';

function NavButton({ to, label, icon, active }) {
  return (
    <Button
      component={RouterLink}
      to={to}
      startIcon={icon}
      sx={{
        justifyContent: 'flex-start',
        px: 1.5,
        py: 1,
        color: active ? 'primary.main' : 'text.secondary',
        bgcolor: active ? 'rgba(14, 94, 111, 0.08)' : 'transparent',
        '&:hover': { bgcolor: 'rgba(14, 94, 111, 0.06)' },
      }}
    >
      {label}
    </Button>
  );
}

export default function App() {
  const { pathname } = useLocation();
  const inQueue = pathname === '/claims' || /^\/claims\/\d+/.test(pathname);

  return (
    <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, minHeight: '100vh' }}>
      <Box
        component="nav"
        aria-label="Main"
        sx={{
          width: { md: 232 },
          flexShrink: 0,
          bgcolor: 'background.paper',
          borderRight: { md: 1 },
          borderBottom: { xs: 1, md: 0 },
          borderColor: 'divider',
          display: 'flex',
          flexDirection: { xs: 'row', md: 'column' },
          alignItems: { xs: 'center', md: 'stretch' },
          gap: 0.5,
          p: 2,
          position: { md: 'sticky' },
          top: 0,
          height: { md: '100vh' },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1, mb: { md: 3 }, mr: { xs: 2, md: 0 } }}>
          <VerifiedUserOutlinedIcon color="primary" />
          <Typography sx={{ fontWeight: 700, fontSize: '1.0625rem' }}>Claim Checker</Typography>
        </Box>

        <NavButton to="/claims" label="Review queue" icon={<InboxOutlinedIcon />} active={inQueue} />
        <NavButton to="/claims/new" label="New claim" icon={<AddPhotoAlternateOutlinedIcon />} active={pathname === '/claims/new'} />

        <Box sx={{ flexGrow: 1 }} />
        {USE_MOCK && (
          <Typography variant="caption" color="text.secondary" sx={{ px: 1, display: { xs: 'none', md: 'block' } }}>
            Showing sample data
          </Typography>
        )}
      </Box>

      <Box component="main" sx={{ flexGrow: 1, minWidth: 0, px: { xs: 2, md: 5 }, py: { xs: 3, md: 5 } }}>
        <Box sx={{ maxWidth: 1100 }}>
          <Routes>
            <Route path="/" element={<Navigate to="/claims" replace />} />
            <Route path="/claims" element={<ClaimsList />} />
            <Route path="/claims/new" element={<NewClaim />} />
            <Route path="/claims/:id" element={<Results />} />
          </Routes>
        </Box>
      </Box>
    </Box>
  );
}