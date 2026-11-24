import { useState } from 'react';
import { Alert, Box, Slider, Tab, Tabs, Typography } from '@mui/material';
import { assetUrl } from '../api/claims';
import { moduleInfo } from '../utils/modules';
import SafeImage from './SafeImage';

const tag = {
  position: 'absolute', top: 8, px: 1, py: 0.25, borderRadius: 1,
  bgcolor: 'rgba(27, 36, 48, 0.75)', color: '#fff', fontSize: '0.75rem', fontWeight: 600, lineHeight: 1.6,
};

export default function EvidenceViewer({ imageUrl, modules }) {
  const maps = modules.filter((m) => m.artifacts?.heatmap_url);
  const [tab, setTab] = useState(0);
  const [pos, setPos] = useState(50);
  const [badPhoto, setBadPhoto] = useState(null);      // photo URL that failed to load
  const [badMaps, setBadMaps] = useState([]);          // heatmap URLs that failed to load

  const photoSrc = assetUrl(imageUrl);
  const frame = { position: 'relative', borderRadius: 1, overflow: 'hidden', border: 1, borderColor: 'divider', lineHeight: 0 };

  // Photo itself missing: show a message, no heatmap overlay
  if (!photoSrc || badPhoto === photoSrc) {
    return (
      <Box sx={frame}>
        <SafeImage src={null} alt="Claim photo" fallbackText="This photo couldn't be loaded from the server." />
      </Box>
    );
  }

  const active = maps[Math.min(tab, maps.length - 1)];
  const mapSrc = active ? assetUrl(active.artifacts.heatmap_url) : null;
  const mapOk = Boolean(mapSrc) && !badMaps.includes(mapSrc);
  const label = active ? moduleInfo(active.module).label : '';

  const photo = (
    <Box component="img" src={photoSrc} alt="Original photo"
         onError={() => setBadPhoto(photoSrc)} sx={{ width: '100%', display: 'block' }} />
  );

  if (!active) return <Box sx={frame}>{photo}</Box>;

  return (
    <Box>
      <Tabs value={Math.min(tab, maps.length - 1)} onChange={(_, v) => setTab(v)} variant="scrollable" sx={{ mb: 1.5 }}>
        {maps.map((m) => <Tab key={m.module} label={moduleInfo(m.module).label} />)}
      </Tabs>

      <Box sx={frame}>
        {photo}
        {mapOk && (
          <>
            <Box
              component="img"
              src={mapSrc}
              alt={`${label} heatmap`}
              onError={() => setBadMaps((list) => [...list, mapSrc])}
              sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill', clipPath: `inset(0 ${100 - pos}% 0 0)` }}
            />
            <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: `${pos}%`, width: 2, bgcolor: '#fff', boxShadow: '0 0 0 1px rgba(0,0,0,0.35)' }} />
            <Box sx={{ ...tag, left: 8 }}>Heatmap</Box>
            <Box sx={{ ...tag, right: 8 }}>Original</Box>
          </>
        )}
      </Box>

      {mapOk ? (
        <>
          <Slider value={pos} onChange={(_, v) => setPos(v)} aria-label="Reveal heatmap" sx={{ mt: 1 }} />
          <Typography variant="body2" color="text.secondary">
            Drag to compare. Bright areas in the heatmap are where {label.toLowerCase()} found something unusual.
          </Typography>
        </>
      ) : (
        <Alert severity="info" sx={{ mt: 1.5 }}>
          The {label.toLowerCase()} heatmap couldn't be loaded. The score and flags on the right still apply.
        </Alert>
      )}
    </Box>
  );
}
