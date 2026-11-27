// Staff-only photo viewer: zoom, pan, reset, a heatmap overlay with a transparency
// slider, and "Open full size". Never use on claimant pages (it shows heatmaps).
import { useRef, useState } from 'react';
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch';
import { Alert, Box, Button, IconButton, Slider, ToggleButton, ToggleButtonGroup, Tooltip, Typography } from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { assetUrl } from '../api';
import { moduleInfo } from '../utils/modules';
import SafeImage from './SafeImage';

const MAX_ZOOM = 8;
const NONE = 'none';

export default function PhotoViewer({ imageUrl, modules }) {
  const maps = modules.filter((m) => m.artifacts?.heatmap_url);
  const zoom = useRef(null);
  const [scale, setScale] = useState(1);
  const [overlay, setOverlay] = useState(maps[0]?.module ?? NONE);   // which heatmap is shown, or none
  const [opacity, setOpacity] = useState(50);
  const [badPhoto, setBadPhoto] = useState(false);
  const [badMaps, setBadMaps] = useState([]);                         // heatmap URLs that failed to load

  const photoSrc = assetUrl(imageUrl);
  const frame = { borderRadius: 1, overflow: 'hidden', border: 1, borderColor: 'divider', bgcolor: '#1b2430', lineHeight: 0 };

  if (!photoSrc || badPhoto) {
    return (
      <Box sx={frame}>
        <SafeImage src={null} alt="Claim photo" fallbackText="This photo couldn't be loaded from the server." />
      </Box>
    );
  }

  const active = maps.find((m) => m.module === overlay);
  const mapSrc = active ? assetUrl(active.artifacts.heatmap_url) : null;
  const mapOk = Boolean(mapSrc) && !badMaps.includes(mapSrc);
  const label = active ? moduleInfo(active.module).label : '';

  return (
    <Box>
      {maps.length > 0 && (
        <ToggleButtonGroup exclusive size="small" value={overlay} onChange={(_, v) => v && setOverlay(v)}
                           aria-label="Heatmap overlay" sx={{ mb: 1.5, flexWrap: 'wrap' }}>
          <ToggleButton value={NONE}>Photo only</ToggleButton>
          {maps.map((m) => <ToggleButton key={m.module} value={m.module}>{moduleInfo(m.module).label}</ToggleButton>)}
        </ToggleButtonGroup>
      )}

      {/* toolbar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1, flexWrap: 'wrap' }}>
        <Tooltip title="Zoom out"><span>
          <IconButton size="small" aria-label="Zoom out" onClick={() => zoom.current?.zoomOut()} disabled={scale <= 1}>
            <ZoomOutIcon />
          </IconButton>
        </span></Tooltip>
        <Typography variant="body2" sx={{ minWidth: 48, textAlign: 'center', fontVariantNumeric: 'tabular-nums' }}
                    aria-live="polite">{Math.round(scale * 100)}%</Typography>
        <Tooltip title="Zoom in"><span>
          <IconButton size="small" aria-label="Zoom in" onClick={() => zoom.current?.zoomIn()} disabled={scale >= MAX_ZOOM}>
            <ZoomInIcon />
          </IconButton>
        </span></Tooltip>
        <Button size="small" startIcon={<RestartAltIcon />} onClick={() => zoom.current?.resetTransform()} disabled={scale === 1}>
          Reset
        </Button>
        <Box sx={{ flexGrow: 1 }} />
        <Button size="small" component="a" href={photoSrc} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNewIcon />}>
          Open full size
        </Button>
        {mapOk && (
          <Button size="small" component="a" href={mapSrc} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNewIcon />}>
            Heatmap
          </Button>
        )}
      </Box>

      <Box sx={{ ...frame, cursor: scale > 1 ? 'grab' : 'zoom-in' }}>
        <TransformWrapper ref={zoom} minScale={1} maxScale={MAX_ZOOM} doubleClick={{ step: 1 }}
                          wheel={{ step: 0.15 }} onTransformed={(_, state) => setScale(state.scale)}>
          <TransformComponent wrapperStyle={{ width: '100%' }} contentStyle={{ width: '100%' }}>
            <Box sx={{ position: 'relative', width: '100%' }}>
              <Box component="img" src={photoSrc} alt="Claim photo" draggable={false}
                   onError={() => setBadPhoto(true)} sx={{ width: '100%', display: 'block' }} />
              {mapOk && (
                <Box component="img" src={mapSrc} alt={`${label} heatmap`} draggable={false}
                     onError={() => setBadMaps((list) => [...list, mapSrc])}
                     sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill',
                           opacity: opacity / 100, pointerEvents: 'none' }} />
              )}
            </Box>
          </TransformComponent>
        </TransformWrapper>
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
        Scroll or pinch to zoom, drag to move around, double-click to zoom in.
      </Typography>

      {active && (mapOk ? (
        <Box sx={{ mt: 1.5 }}>
          <Typography id="heatmap-opacity" variant="body2" sx={{ fontWeight: 600 }}>
            {label} heatmap: {opacity}% visible
          </Typography>
          <Slider value={opacity} onChange={(_, v) => setOpacity(v)} min={0} max={100} step={5}
                  aria-labelledby="heatmap-opacity" />
          <Typography variant="body2" color="text.secondary">
            Bright areas are where {label.toLowerCase()} found something unusual.
          </Typography>
        </Box>
      ) : (
        <Alert severity="info" sx={{ mt: 1.5 }}>
          The {label.toLowerCase()} heatmap couldn't be loaded. The score and flags still apply.
        </Alert>
      ))}
    </Box>
  );
}
