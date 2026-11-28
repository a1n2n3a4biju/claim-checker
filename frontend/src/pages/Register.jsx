import { useState } from 'react';
import { Link as RouterLink, Navigate, useNavigate } from 'react-router-dom';
import { Alert, Box, Button, Link, Paper, TextField, Typography } from '@mui/material';
import { errorText } from '../api';
import { HOME, useAuth } from '../auth/AuthContext';

const MIN_PASSWORD = 8;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// New customer account. Calls POST /auth/register; the backend stores only a bcrypt hash of the password.
export default function Register() {
  const { user, ready, signUp } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (ready && user) return <Navigate to={HOME[user.role]} replace />;

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }));
    setFieldErrors((fe) => ({ ...fe, [key]: '' }));
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const errs = {};
    if (!form.name.trim()) errs.name = 'Enter your full name';
    if (!EMAIL_RE.test(form.email.trim())) errs.email = 'Enter a valid email address';
    if (form.password.length < MIN_PASSWORD) errs.password = `Use at least ${MIN_PASSWORD} characters`;
    if (form.confirm !== form.password) errs.confirm = "The passwords don't match";
    setFieldErrors(errs);
    if (Object.keys(errs).length) return;

    setBusy(true);
    try {
      const newUser = await signUp(form.name.trim(), form.email.trim(), form.password);
      navigate(HOME[newUser.role], { replace: true, state: { welcome: true } });
    } catch (err) {
      // 422 names the field: show it next to that field
      const field = err?.status === 422 && ['name', 'email', 'password'].find((k) => err.detail?.startsWith(k));
      if (field) setFieldErrors((fe) => ({ ...fe, [field]: err.detail.replace(/^\w+: /, '') }));
      else setError(errorText(err));
      setBusy(false);
    }
  };

  return (
    <Paper component="form" onSubmit={submit} noValidate
           sx={{ maxWidth: 460, mx: 'auto', mt: { xs: 2, md: 4 }, p: { xs: 3, md: 5 } }}>
      <Typography variant="h4" component="h1" sx={{ mb: 1 }}>Create an account</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        For customers who want to make and track claims.
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <TextField label="Full name" autoComplete="name" fullWidth required autoFocus value={form.name} onChange={set('name')}
                 error={!!fieldErrors.name} helperText={fieldErrors.name || ' '} sx={{ mb: 1 }} />
      <TextField label="Email" type="email" autoComplete="email" fullWidth required value={form.email} onChange={set('email')}
                 error={!!fieldErrors.email} helperText={fieldErrors.email || ' '} sx={{ mb: 1 }} />
      <TextField label="Password" type="password" autoComplete="new-password" fullWidth required value={form.password}
                 onChange={set('password')} error={!!fieldErrors.password}
                 helperText={fieldErrors.password || `At least ${MIN_PASSWORD} characters`} sx={{ mb: 1 }} />
      <TextField label="Confirm password" type="password" autoComplete="new-password" fullWidth required value={form.confirm}
                 onChange={set('confirm')} error={!!fieldErrors.confirm} helperText={fieldErrors.confirm || ' '} sx={{ mb: 2 }} />
      <Button type="submit" variant="contained" size="large" fullWidth disabled={busy}>
        {busy ? 'Creating your account…' : 'Create account'}
      </Button>
      <Box sx={{ mt: 3, textAlign: 'center' }}>
        <Typography variant="body2">
          Already have an account? <Link component={RouterLink} to="/login" sx={{ fontWeight: 600 }}>Sign in</Link>
        </Typography>
      </Box>
    </Paper>
  );
}
