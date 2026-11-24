import { useState } from 'react';
import { Box, Typography } from '@mui/material';

// An <img> that shows a short message instead of a broken image when loading fails.
export default function SafeImage({ src, alt, sx, fallbackText = "Image couldn't be loaded" }) {
  const [failedSrc, setFailedSrc] = useState(null);

  if (!src || failedSrc === src) {
    return (
      <Box
        role="img"
        aria-label={alt}
        sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
          bgcolor: 'background.default', color: 'text.secondary', aspectRatio: '4 / 3', width: '100%', p: 2,
          ...sx,
        }}
      >
        <Typography variant="body2">{fallbackText}</Typography>
      </Box>
    );
  }

  return <Box component="img" src={src} alt={alt} onError={() => setFailedSrc(src)} sx={sx} />;
}
