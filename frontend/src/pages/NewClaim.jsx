import { useEffect, useRef, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Alert, Box, Button, IconButton, LinearProgress, Paper, TextField, Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import AddPhotoAlternateOutlinedIcon from '@mui/icons-material/AddPhotoAlternateOutlined';
import { analyzeClaim, createClaim, uploadImages } from '../api/claims';

const MAX_FILES = 10;
const MAX_MB = 10;
const isJpeg = (f) => f.type === 'image/jpeg' || /\.jpe?g$/i.test(f.name);
const today = new Date().toISOString().slice(0, 10);
const formatSize = (bytes) =>
  bytes < 1024 * 1024 ? `${Math.round(bytes / 1024)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;

const stageText = {
  creating: 'Creating the claim…',
  uploading: 'Uploading photos…',
  analyzing: 'Checking your photos… This can take up to a minute.',
};

function Section({ title, children }) {
  return (
    <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
      <Typography variant="h6" component="h2" sx={{ mb: 2 }}>{title}</Typography>
      {children}
    </Paper>
  );
}

export default function NewClaim() {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const photosRef = useRef([]);

  const [form, setForm] = useState({ claimant_name: '', incident_date: '', description: '' });
  const [photos, setPhotos] = useState([]);           // { id, file, url }
  const [fileMessage, setFileMessage] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [touched, setTouched] = useState(false);
  const [stage, setStage] = useState(null);           // null | 'creating' | 'uploading' | 'analyzing'
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');

  // Free the preview URLs when leaving the page
  useEffect(() => { photosRef.current = photos; }, [photos]);
  useEffect(() => () => photosRef.current.forEach((p) => URL.revokeObjectURL(p.url)), []);

  const busy = stage !== null;
  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const addFiles = (fileList) => {
    const incoming = Array.from(fileList);
    const notJpeg = incoming.filter((f) => !isJpeg(f)).map((f) => f.name);
    const tooBig = incoming.filter((f) => isJpeg(f) && f.size > MAX_MB * 1024 * 1024).map((f) => f.name);
    const usable = incoming
      .filter((f) => isJpeg(f) && f.size <= MAX_MB * 1024 * 1024)
      .filter((f) => !photos.some((p) => p.file.name === f.name && p.file.size === f.size));
    const room = MAX_FILES - photos.length;
    const added = usable.slice(0, room).map((f) => ({
      id: `${f.name}-${f.size}-${f.lastModified}`,
      file: f,
      url: URL.createObjectURL(f),
    }));
    setPhotos((prev) => [...prev, ...added]);

    const messages = [];
    if (notJpeg.length) messages.push(`Only JPEG photos can be checked. Skipped: ${notJpeg.join(', ')}.`);
    if (tooBig.length) messages.push(`Each photo must be under ${MAX_MB} MB. Skipped: ${tooBig.join(', ')}.`);
    if (usable.length > room) messages.push(`A claim can have up to ${MAX_FILES} photos.`);
    setFileMessage(messages.join(' '));
  };

  const removePhoto = (id) => {
    const photo = photos.find((p) => p.id === id);
    if (photo) URL.revokeObjectURL(photo.url);
    setPhotos(photos.filter((p) => p.id !== id));
  };

  const errors = {
    claimant_name: form.claimant_name.trim() ? '' : "Enter the claimant's name.",
    incident_date: !form.incident_date
      ? 'Choose the date of the incident.'
      : form.incident_date > today ? "The incident date can't be in the future." : '',
    photos: photos.length ? '' : 'Add at least one photo of the damage.',
  };
  const valid = !Object.values(errors).some(Boolean);
  const show = (field) => (touched ? errors[field] : '');

  const submit = async (e) => {
    e.preventDefault();
    setTouched(true);
    if (!valid || busy) return;
    setError('');
    try {
      setStage('creating');
      const claim = await createClaim({
        claimant_name: form.claimant_name.trim(),
        incident_date: form.incident_date,
        description: form.description.trim(),
      });
      setStage('uploading');
      setProgress(0);
      await uploadImages(claim.id, photos.map((p) => p.file), setProgress);
      setStage('analyzing');
      await analyzeClaim(claim.id);
      navigate(`/submitted/${claim.id}`, {
        state: { trackingCode: claim.tracking_code, photos: photos.length, name: form.claimant_name.trim() },
      });
    } catch (err) {
      const detail = err?.response?.data?.detail ?? err.message;
      setError(`Your claim wasn't submitted: ${detail}. Please try again in a moment.`);
      setStage(null);
    }
  };

  return (
    <Box component="form" noValidate onSubmit={submit} sx={{ maxWidth: 760 }}>
      <Typography variant="h4" component="h1">Submit a claim</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Tell us what happened and add photos of the damage. You'll get a claim number and a tracking code to check its status.
      </Typography>

      <Section title="Claim details">
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 200px' }, gap: 2 }}>
          <TextField
            label="Your name"
            value={form.claimant_name}
            onChange={update('claimant_name')}
            error={Boolean(show('claimant_name'))}
            helperText={show('claimant_name')}
            disabled={busy}
            required
          />
          <TextField
            label="Incident date"
            type="date"
            value={form.incident_date}
            onChange={update('incident_date')}
            error={Boolean(show('incident_date'))}
            helperText={show('incident_date')}
            disabled={busy}
            required
            slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: today } }}
          />
          <TextField
            label="What happened"
            value={form.description}
            onChange={update('description')}
            disabled={busy}
            multiline
            minRows={3}
            placeholder="For example: my rear bumper was hit while parked outside the office"
            sx={{ gridColumn: '1 / -1' }}
          />
        </Box>
      </Section>

      <Section title="Photos">
        <Box
          role="button"
          tabIndex={0}
          aria-label="Add photos"
          onClick={() => !busy && inputRef.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !busy) { e.preventDefault(); inputRef.current?.click(); }
          }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); if (!busy) addFiles(e.dataTransfer.files); }}
          sx={{
            border: 2,
            borderStyle: 'dashed',
            borderColor: dragOver ? 'primary.main' : show('photos') ? 'error.main' : 'divider',
            bgcolor: dragOver ? 'rgba(14, 94, 111, 0.06)' : 'background.default',
            borderRadius: 1,
            p: 4,
            textAlign: 'center',
            cursor: busy ? 'default' : 'pointer',
          }}
        >
          <AddPhotoAlternateOutlinedIcon color="primary" sx={{ fontSize: 36, mb: 1 }} />
          <Typography sx={{ fontWeight: 600 }}>Drag photos here, or click to choose</Typography>
          <Typography variant="body2" color="text.secondary">
            JPEG only, up to {MAX_FILES} photos, {MAX_MB} MB each
          </Typography>
        </Box>
        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,image/jpeg"
          multiple
          hidden
          onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }}
        />

        {show('photos') && <Typography variant="body2" color="error" sx={{ mt: 1 }}>{show('photos')}</Typography>}
        {fileMessage && <Alert severity="warning" sx={{ mt: 2 }} onClose={() => setFileMessage('')}>{fileMessage}</Alert>}

        {photos.length > 0 && (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 3, mb: 1 }}>
              {photos.length} of {MAX_FILES} photos added
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 2 }}>
              {photos.map((p) => (
                <Box key={p.id} sx={{ position: 'relative' }}>
                  <Box
                    component="img"
                    src={p.url}
                    alt={p.file.name}
                    sx={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', borderRadius: 1, display: 'block', border: 1, borderColor: 'divider' }}
                  />
                  <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }} noWrap title={p.file.name}>
                    {p.file.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">{formatSize(p.file.size)}</Typography>
                  {!busy && (
                    <IconButton
                      size="small"
                      aria-label={`Remove ${p.file.name}`}
                      onClick={() => removePhoto(p.id)}
                      sx={{ position: 'absolute', top: 6, right: 6, bgcolor: 'background.paper', '&:hover': { bgcolor: 'background.paper' } }}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  )}
                </Box>
              ))}
            </Box>
          </>
        )}
      </Section>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {busy && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {stageText[stage]}{stage === 'uploading' ? ` ${progress}%` : ''}
          </Typography>
          <LinearProgress
            variant={stage === 'uploading' ? 'determinate' : 'indeterminate'}
            value={progress}
          />
        </Box>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1.5 }}>
        <Button component={RouterLink} to="/" disabled={busy}>Cancel</Button>
        <Button type="submit" variant="contained" disabled={busy}>Submit claim</Button>
      </Box>
    </Box>
  );
}
