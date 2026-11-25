import { useState } from 'react';
import { Alert, Box, Button, Paper, TextField, Typography } from '@mui/material';
import { keyframes } from '@mui/material/styles';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlined';
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import { submitDecision } from '../api/claims';
import { useAuth } from '../auth/AuthContext';
import { serif, stamp } from '../theme';

const intro = {
  low: 'Low risk: this claim can move to fast processing without review, but you can still record a decision.',
  medium: 'Check the evidence below, then approve the claim or escalate it to the fraud team.',
  high: 'High risk: check the evidence carefully before deciding. Escalate if anything looks manipulated.',
};

// decided_at arrives in UTC (ending +00:00); show it in the viewer's local time
const formatWhen = (iso) =>
  iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';

// A decision is stamped on the claim, like an ink stamp on a case file.
const stampIn = keyframes`
  from { opacity: 0; transform: rotate(-4deg) scale(1.3); }
  to   { opacity: 0.94; transform: rotate(-4deg) scale(1); }
`;

function DecisionStamp({ approved, who, when, animate }) {
  const color = approved ? stamp.approved : stamp.escalated;
  return (
    <Box
      role="img"
      aria-label={`${approved ? 'Approved' : 'Escalated'}${who ? ` by ${who}` : ''}${when ? `, ${when}` : ''}`}
      sx={{
        flexShrink: 0,
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        minWidth: 170,
        px: 2.5,
        py: 1.25,
        color,
        border: `3px solid ${color}`,
        borderRadius: '10px',
        boxShadow: `inset 0 0 0 2px #fff, inset 0 0 0 3px ${color}`,
        transform: 'rotate(-4deg)',
        opacity: 0.94,
        animation: animate ? `${stampIn} 280ms ease-out` : 'none',
      }}
    >
      <Typography sx={{ fontFamily: serif, fontWeight: 700, fontSize: '1.5rem', lineHeight: 1.1, color: 'inherit' }}>
        {approved ? 'Approved' : 'Escalated'}
      </Typography>
      {who && <Typography variant="body2" sx={{ fontWeight: 600, color: 'inherit' }}>{who}</Typography>}
      {when && <Typography variant="caption" sx={{ color: 'inherit' }}>{when}</Typography>}
    </Box>
  );
}

export default function ReviewPanel({ claimId, risk, decision, note, reviewerName, decidedAt, onSaved }) {
  const { session, openSignIn, signOut } = useAuth();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(null);       // 'approved' | 'escalated' | null
  const [error, setError] = useState('');
  const [authMessage, setAuthMessage] = useState('');
  const [noteError, setNoteError] = useState('');
  const [justDecided, setJustDecided] = useState(false);   // play the stamp animation once, after a decision

  if (!risk) return null;                           // decisions need an analyzed claim

  // ---------- a decision is recorded
  if (decision && !editing) {
    const approved = decision === 'approved';
    const startEditing = () => {
      if (!session) { openSignIn(); return; }
      setText(note ?? '');
      setJustDecided(false);
      setEditing(true);
    };
    return (
      <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3, display: 'flex', gap: { xs: 2, md: 4 }, alignItems: 'center', flexWrap: 'wrap' }}>
        <DecisionStamp approved={approved} who={reviewerName} when={formatWhen(decidedAt)} animate={justDecided} />
        <Box sx={{ flexGrow: 1, minWidth: 220 }}>
          <Typography sx={{ fontWeight: 600, mb: 0.5 }}>
            {approved ? 'Approved for processing' : 'Sent to the fraud team'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {note ? `Note: ${note}` : 'No note was added.'}
          </Typography>
        </Box>
        <Button onClick={startEditing}>{session ? 'Change decision' : 'Sign in to change'}</Button>
      </Paper>
    );
  }

  // ---------- not signed in: no decision form
  if (!session) {
    return (
      <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
        <Typography variant="h6" component="h2">Reviewer decision</Typography>
        {authMessage && <Alert severity="warning" sx={{ my: 1.5 }}>{authMessage}</Alert>}
        <Typography color="text.secondary" sx={{ mb: 2 }}>Sign in to approve or escalate this claim.</Typography>
        <Button variant="contained" onClick={openSignIn}>Sign in as reviewer</Button>
      </Paper>
    );
  }

  // ---------- signed in: decision form
  const decide = async (choice) => {
    if (choice === 'escalated' && !text.trim()) {
      setNoteError('Add a note explaining why, so the fraud team knows what to look at.');
      return;
    }
    setNoteError('');
    setError('');
    setSaving(choice);
    try {
      await submitDecision(claimId, choice, text.trim(), session);
      setEditing(false);
      setAuthMessage('');
      setJustDecided(true);
      await onSaved();
    } catch (e) {
      const detail = e?.response?.data?.detail ?? e.message;
      if (e?.response?.status === 401) {
        signOut();                                   // the token is no longer valid
        setAuthMessage(`${detail}. Sign in to approve or escalate.`);
      } else {
        setError(`The decision wasn't saved: ${detail}. Try again.`);
      }
    } finally {
      setSaving(null);
    }
  };

  return (
    <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
      <Typography variant="h6" component="h2">Reviewer decision</Typography>
      <Typography color="text.secondary" sx={{ mb: 0.5 }}>{intro[risk]}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Deciding as {session.name}</Typography>

      <TextField
        label="Note"
        placeholder="For example: damage pattern matches the description; or: rear bumper area looks pasted in"
        value={text}
        onChange={(e) => { setText(e.target.value); if (noteError) setNoteError(''); }}
        error={Boolean(noteError)}
        helperText={noteError || 'Required when escalating, optional when approving.'}
        multiline
        minRows={2}
        fullWidth
        disabled={saving !== null}
        sx={{ mb: 2 }}
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
        {editing && <Button onClick={() => setEditing(false)} disabled={saving !== null}>Cancel</Button>}
        <Button variant="outlined" color="success" startIcon={<CheckCircleOutlineIcon />}
                onClick={() => decide('approved')} disabled={saving !== null}>
          {saving === 'approved' ? 'Saving…' : 'Approve claim'}
        </Button>
        <Button variant="contained" color="error" startIcon={<FlagOutlinedIcon />}
                onClick={() => decide('escalated')} disabled={saving !== null}>
          {saving === 'escalated' ? 'Saving…' : 'Escalate to fraud team'}
        </Button>
      </Box>
    </Paper>
  );
}
