import { useState } from 'react';
import { Link as RouterLink, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Alert, Button, Link, Paper, TextField, Typography } from '@mui/material';
import { errorText } from '../api';
import { HOME, useAuth } from '../auth/AuthContext';


export default function Login() {
  const { user, ready, notice, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (ready && user) return <Navigate to={HOME[user.role]} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    if (!email.trim() || !password) {
      setError('Enter your email and password');
      return;
    }
    setBusy(true);
    try {
      const signedIn = await signIn(email.trim(), password);
      // go back to the page that asked for sign-in, if it belongs to this role
      const from = location.state?.from;
      const ownArea = { claimant: '/my/', assessor: '/assessor/', insurer: '/insurer/' }[signedIn.role];
      navigate(from && from.startsWith(ownArea) ? from : HOME[signedIn.role], { replace: true });
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Paper component="form" onSubmit={submit} noValidate
           sx={{ maxWidth: 440, mx: 'auto', mt: { xs: 2, md: 6 }, p: { xs: 3, md: 5 } }}>
      <Typography variant="h4" component="h1" sx={{ mb: 1 }}>Sign in</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Customers, garage assessors and the insurance team all sign in here.
      </Typography>
      {notice && !error && <Alert severity="warning" sx={{ mb: 2 }}>{notice}</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <TextField label="Email" type="email" autoComplete="username" fullWidth required autoFocus
                 value={email} onChange={(e) => setEmail(e.target.value)} sx={{ mb: 2 }} />
      <TextField label="Password" type="password" autoComplete="current-password" fullWidth required
                 value={password} onChange={(e) => setPassword(e.target.value)} sx={{ mb: 3 }} />
      <Button type="submit" variant="contained" size="large" fullWidth disabled={busy}>
        {busy ? 'Signing in…' : 'Sign in'}
      </Button>
      <Typography variant="body2" sx={{ mt: 3, textAlign: 'center' }}>
        New customer? <Link component={RouterLink} to="/register" sx={{ fontWeight: 600 }}>Create an account</Link>
      </Typography>
    </Paper>
  );
}
