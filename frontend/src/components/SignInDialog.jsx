import { useEffect, useState } from 'react';
import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, TextField, Typography,
} from '@mui/material';
import { getReviewers } from '../api/claims';
import { useAuth } from '../auth/AuthContext';

const message = (e) => {
  if (!e?.response) return "Can't reach the server. Check that the backend is running.";
  return e.response.data?.detail ?? `Sign-in failed (error ${e.response.status}).`;
};

export default function SignInDialog() {
  const { dialogOpen, closeSignIn, signIn } = useAuth();
  const [names, setNames] = useState([]);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!dialogOpen) return;
    let ignore = false;
    getReviewers()
      .then((list) => { if (!ignore) setNames(list); })
      .catch((e) => { if (!ignore) setError(message(e)); });
    return () => { ignore = true; };
  }, [dialogOpen]);

  const close = () => {
    setPassword('');
    setError('');
    closeSignIn();
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!username || !password) { setError('Choose your name and enter the reviewer password.'); return; }
    setBusy(true);
    setError('');
    try {
      await signIn(username, password);
      close();
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={dialogOpen} onClose={busy ? undefined : close} fullWidth maxWidth="xs">
      <form onSubmit={submit} noValidate>
        <DialogTitle>Reviewer sign-in</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Only reviewers can approve or escalate claims. Anyone can submit a claim without signing in.
          </Typography>
          <TextField
            select
            label="Reviewer"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            fullWidth
            disabled={busy}
            sx={{ mb: 2 }}
          >
            {names.map((n) => <MenuItem key={n} value={n}>{n}</MenuItem>)}
          </TextField>
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            fullWidth
            disabled={busy}
            autoComplete="current-password"
          />
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={close} disabled={busy}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
