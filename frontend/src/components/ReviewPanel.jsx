import { useState } from 'react';
import { Alert, Box, Button, Paper, TextField, Typography } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlined';
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import { submitDecision } from '../api/claims';

const intro = {
  low: 'Low risk: this claim can move to fast processing without review, but you can still record a decision.',
  medium: 'Check the evidence below, then approve the claim or escalate it to the fraud team.',
  high: 'High risk: check the evidence carefully before deciding. Escalate if anything looks manipulated.',
};

export default function ReviewPanel({ claimId, risk, decision, note, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(null);       // 'approved' | 'escalated' | null
  const [error, setError] = useState('');
  const [noteError, setNoteError] = useState('');

  if (!risk) return null;                           // decisions need an analyzed claim

  if (decision && !editing) {
    const approved = decision === 'approved';
    return (
      <Paper sx={{ p: 2.5, mb: 3, display: 'flex', gap: 2, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        {approved ? <CheckCircleOutlineIcon color="success" /> : <FlagOutlinedIcon color="error" />}
        <Box sx={{ flexGrow: 1, minWidth: 220 }}>
          <Typography sx={{ fontWeight: 600 }}>
            {approved ? 'Approved by reviewer' : 'Escalated to the fraud team'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {note ? `Note: ${note}` : 'No note was added.'}
          </Typography>
        </Box>
        <Button onClick={() => { setText(note ?? ''); setEditing(true); }}>Change decision</Button>
      </Paper>
    );
  }

  const decide = async (choice) => {
    if (choice === 'escalated' && !text.trim()) {
      setNoteError('Add a note explaining why, so the fraud team knows what to look at.');
      return;
    }
    setNoteError('');
    setError('');
    setSaving(choice);
    try {
      await submitDecision(claimId, choice, text.trim());
      setEditing(false);
      await onSaved();
    } catch (e) {
      setError(`The decision wasn't saved: ${e?.response?.data?.detail ?? e.message}. Try again.`);
    } finally {
      setSaving(null);
    }
  };

  return (
    <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
      <Typography variant="h6" component="h2">Reviewer decision</Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>{intro[risk]}</Typography>

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