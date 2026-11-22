import { useState } from 'react';
import { Box, Slider, Tab, Tabs, Typography } from '@mui/material';
import { assetUrl } from '../api/claims';
import { moduleInfo } from '../utils/modules';

const tag = {
  position: 'absolute', top: 8, px: 1, py: 0.25, borderRadius: 1,
  bgcolor: 'rgba(27, 36, 48, 0.75)', color: '#fff', fontSize: '0.75rem', fontWeight: 600, lineHeight: 1.6,
};

export default function EvidenceViewer({ imageUrl, modules }) {
  const maps = modules.filter((m) => m.artifacts?.heatmap_url);
  const [tab, setTab] = useState(0);
  const [pos, setPos] = useState(50);
  const active = maps[Math.min(tab, maps.length - 1)];

  const frame = { position: 'relative', borderRadius: 1, overflow: 'hidden', border: 1, borderColor: 'divider', lineHeight: 0 };

  if (!active) {
    return (
      <Box sx={frame}>
        <Box component="img" src={assetUrl(imageUrl)} alt="Claim photo" sx={{ width: '100%', display: 'block' }} />
      </Box>
    );
  }

  const label = moduleInfo(active.module).label;

  return (
    <Box>
      <Tabs value={Math.min(tab, maps.length - 1)} onChange={(_, v) => setTab(v)} variant="scrollable" sx={{ mb: 1.5 }}>
        {maps.map((m) => <Tab key={m.module} label={moduleInfo(m.module).label} />)}
      </Tabs>

      <Box sx={frame}>
        <Box component="img" src={assetUrl(imageUrl)} alt="Original photo" sx={{ width: '100%', display: 'block' }} />
        <Box
          component="img"
          src={assetUrl(active.artifacts.heatmap_url)}
          alt={`${label} heatmap`}
          sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill', clipPath: `inset(0 ${100 - pos}% 0 0)` }}
        />
        <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: `${pos}%`, width: 2, bgcolor: '#fff', boxShadow: '0 0 0 1px rgba(0,0,0,0.35)' }} />
        <Box sx={{ ...tag, left: 8 }}>Heatmap</Box>
        <Box sx={{ ...tag, right: 8 }}>Original</Box>
      </Box>

      <Slider value={pos} onChange={(_, v) => setPos(v)} aria-label="Reveal heatmap" sx={{ mt: 1 }} />
      <Typography variant="body2" color="text.secondary">
        Drag to compare. Bright areas in the heatmap are where {label.toLowerCase()} found something unusual.
      </Typography>
    </Box>
  );
}