import { Navigate, useLocation } from 'react-router-dom';
import { Button, Paper, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { HOME, useAuth } from '../auth/AuthContext';
import { Loading } from './shared';

export function NoAccess() {
  const { user } = useAuth();
  return (
    <Paper sx={{ maxWidth: 520, mx: 'auto', mt: 6, p: 5, textAlign: 'center' }}>
      <Typography variant="h5" component="h1" sx={{ mb: 1 }}>You don't have access to this</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>This page is for a different kind of account.</Typography>
      {user && <Button variant="contained" component={RouterLink} to={HOME[user.role]}>Go to my home page</Button>}
    </Paper>
  );
}

// Protects a page by role: not signed in -> login page; wrong role -> "You don't have access to this"
export default function RequireRole({ role, children }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.role !== role) return <NoAccess />;
  return children;
}
