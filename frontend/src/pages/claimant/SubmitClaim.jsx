import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Box, Button, LinearProgress, MenuItem, Paper, TextField, Typography } from '@mui/material';
import { createClaim, errorText, getMyPolicies, uploadImages } from '../../api';
import PhotoPicker from '../../components/PhotoPicker';
import { ErrorBox, Loading, PageTitle } from '../../components/shared';
import { capitalise, formatDate, todayIso } from '../../utils/format';
import { SEVERITIES } from '../../utils/status';
import useLoad from '../../utils/useLoad';

const EMPTY = { vehicle_id: '', incident_date: '', incident_time: '', location: '', severity: '', description: '' };
const REQUIRED = {
  vehicle_id: 'Choose a vehicle', incident_date: 'Enter the date', incident_time: 'Enter the time',
  location: 'Enter where it happened', severity: 'Choose how bad the damage is', description: 'Describe what happened',
};

// Vehicle dropdown (from my policies), date, time, location, severity, description, JPEG photos.
// Calls POST /claims, then POST /claims/{id}/images.
export default function SubmitClaim() {
  const navigate = useNavigate();
  const { data: policies, error: loadError, loading } = useLoad(useCallback(() => getMyPolicies(), []));
  const [form, setForm] = useState(EMPTY);
  const [files, setFiles] = useState([]);
  const [fieldErrors, setFieldErrors] = useState({});
  const [photoError, setPhotoError] = useState('');
  const [error, setError] = useState('');
  const [step, setStep] = useState('');            // '', 'creating', 'uploading'
  const [progress, setProgress] = useState(0);
  const [createdId, setCreatedId] = useState(null); // claim created but photos not uploaded yet

  const vehicles = (policies ?? []).flatMap((p) => p.vehicles.map((v) => ({ ...v, policy: p })));
  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }));
    setFieldErrors((fe) => ({ ...fe, [key]: '' }));
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const missing = Object.fromEntries(Object.entries(REQUIRED).filter(([k]) => !String(form[k]).trim()));
    setFieldErrors(missing);
    if (!files.length) setPhotoError('Add at least one JPEG photo of the damage');
    if (Object.keys(missing).length || !files.length) return;

    try {
      let id = createdId;
      if (!id) {
        setStep('creating');
        const claim = await createClaim({ ...form, vehicle_id: Number(form.vehicle_id), location: form.location.trim(),
                                          description: form.description.trim() });
        id = claim.id;
        setCreatedId(id);
      }
      setStep('uploading');
      await uploadImages(id, files, setProgress);
      navigate(`/my/claims/${id}`, { state: { justSubmitted: true } });
    } catch (err) {
      setStep('');
      // 422 names the field: show it next to that field
      const field = err?.status === 422 && Object.keys(REQUIRED).find((k) => err.detail?.startsWith(k));
      if (field) setFieldErrors((fe) => ({ ...fe, [field]: err.detail }));
      setError(errorText(err));
    }
  };

  if (loading && !policies) return <Loading />;
  const busy = Boolean(step);
  const chosen = vehicles.find((v) => String(v.id) === String(form.vehicle_id));

  return (
    <>
      <PageTitle title="Submit a claim" subtitle="Tell us what happened and add photos of the damage" />
      <ErrorBox error={loadError} />
      {policies && !vehicles.length && <Alert severity="info">There are no vehicles on your policies, so you can't make a claim yet.</Alert>}
      {vehicles.length > 0 && (
        <Paper component="form" noValidate onSubmit={submit} sx={{ p: { xs: 2, md: 4 }, maxWidth: 760 }}>
          {createdId && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Claim #{createdId} was created, but the photos didn't upload. Check them and press the button again.
            </Alert>
          )}
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
            <TextField select label="Vehicle" required value={form.vehicle_id} onChange={set('vehicle_id')} disabled={busy || !!createdId}
                       error={!!fieldErrors.vehicle_id} helperText={fieldErrors.vehicle_id || (chosen
                         ? `Policy ${chosen.policy.policy_number}, valid ${formatDate(chosen.policy.start_date)} to ${formatDate(chosen.policy.end_date)}`
                         : ' ')}
                       sx={{ gridColumn: { sm: '1 / -1' } }}>
              {vehicles.map((v) => (
                <MenuItem key={v.id} value={v.id}>{v.registration} · {v.make} {v.model} ({v.year})</MenuItem>
              ))}
            </TextField>
            <TextField label="Incident date" type="date" required value={form.incident_date} onChange={set('incident_date')}
                       disabled={busy || !!createdId} error={!!fieldErrors.incident_date} helperText={fieldErrors.incident_date || ' '}
                       slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: todayIso() } }} />
            <TextField label="Incident time" type="time" required value={form.incident_time} onChange={set('incident_time')}
                       disabled={busy || !!createdId} error={!!fieldErrors.incident_time} helperText={fieldErrors.incident_time || ' '}
                       slotProps={{ inputLabel: { shrink: true } }} />
            <TextField label="Location" required value={form.location} onChange={set('location')} disabled={busy || !!createdId}
                       placeholder="e.g. Avinashi Road, Coimbatore"
                       error={!!fieldErrors.location} helperText={fieldErrors.location || ' '} />
            <TextField select label="Severity" required value={form.severity} onChange={set('severity')} disabled={busy || !!createdId}
                       error={!!fieldErrors.severity} helperText={fieldErrors.severity || ' '}>
              {SEVERITIES.map((s) => <MenuItem key={s} value={s}>{capitalise(s)}</MenuItem>)}
            </TextField>
            <TextField label="What happened?" required multiline minRows={3} value={form.description} onChange={set('description')}
                       disabled={busy || !!createdId} error={!!fieldErrors.description} helperText={fieldErrors.description || ' '}
                       sx={{ gridColumn: { sm: '1 / -1' } }} />
          </Box>

          <Typography sx={{ fontWeight: 600, mt: 1, mb: 1 }}>Photos of the damage</Typography>
          <PhotoPicker files={files} onChange={(f) => { setFiles(f); if (f.length) setPhotoError(''); }} onError={setPhotoError} />
          {photoError && <Alert severity="error" sx={{ mt: 2 }}>{photoError}</Alert>}

          {busy && (
            <Box sx={{ mt: 3 }}>
              <Typography variant="body2" sx={{ mb: 1 }}>
                {step === 'creating' ? 'Creating your claim…' : `Uploading photos… ${progress}%`}
              </Typography>
              <LinearProgress variant={step === 'uploading' ? 'determinate' : 'indeterminate'} value={progress} />
            </Box>
          )}
          <Box sx={{ display: 'flex', gap: 1.5, mt: 3 }}>
            <Button type="submit" variant="contained" size="large" disabled={busy}>
              {createdId ? 'Upload photos' : 'Submit claim'}
            </Button>
            <Button onClick={() => navigate(createdId ? `/my/claims/${createdId}` : '/my/claims')} disabled={busy}>Cancel</Button>
          </Box>
        </Paper>
      )}
    </>
  );
}
