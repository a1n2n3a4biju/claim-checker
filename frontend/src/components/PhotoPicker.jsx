import { useEffect, useMemo } from 'react';
import { Box, Button, IconButton, Typography } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

export const MAX_PHOTOS = 10;
export const MAX_MB = 10;

const isJpeg = (file) => /^image\/jpe?g$/i.test(file.type) || /\.jpe?g$/i.test(file.name);

// Choose JPEG photos with previews. files / onChange hold File objects; onError gets a message.
export default function PhotoPicker({ files, onChange, onError, label = 'Add JPEG photos' }) {
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const add = (e) => {
    const chosen = Array.from(e.target.files ?? []);
    e.target.value = '';
    const notJpeg = chosen.filter((f) => !isJpeg(f));
    const tooBig = chosen.filter((f) => f.size > MAX_MB * 1024 * 1024);
    const ok = chosen.filter((f) => isJpeg(f) && f.size <= MAX_MB * 1024 * 1024);
    const next = [...files, ...ok].slice(0, MAX_PHOTOS);
    const problems = [];
    if (notJpeg.length) problems.push(`${notJpeg.map((f) => f.name).join(', ')}: only JPEG photos can be uploaded`);
    if (tooBig.length) problems.push(`${tooBig.map((f) => f.name).join(', ')}: larger than ${MAX_MB} MB`);
    if (files.length + ok.length > MAX_PHOTOS) problems.push(`Up to ${MAX_PHOTOS} photos`);
    onError?.(problems.join('. '));
    onChange(next);
  };

  return (
    <Box>
      <Button variant="outlined" component="label">
        {label}
        <input hidden type="file" accept="image/jpeg,.jpg,.jpeg" multiple onChange={add} />
      </Button>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        JPEG only, up to {MAX_PHOTOS} photos, {MAX_MB} MB each.
      </Typography>
      {files.length > 0 && (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 1.5, mt: 2 }}>
          {files.map((f, i) => (
            <Box key={`${f.name}-${i}`} sx={{ position: 'relative', border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'hidden' }}>
              <Box component="img" src={previews[i]} alt={f.name} sx={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', display: 'block' }} />
              <IconButton size="small" aria-label={`Remove ${f.name}`} onClick={() => onChange(files.filter((_, j) => j !== i))}
                          sx={{ position: 'absolute', top: 4, right: 4, bgcolor: 'rgba(255,255,255,0.9)', '&:hover': { bgcolor: '#fff' } }}>
                <CloseIcon fontSize="small" />
              </IconButton>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
