// Shared pieces (team doc, M1 step 3): status badge, timeline, error box and small layout helpers.
import { Alert, Box, Chip, Paper, Skeleton, Typography } from '@mui/material';
import { errorText } from '../api';
import { risk as riskColours } from '../theme';
import { formatDateTime } from '../utils/format';
import { statusLabel } from '../utils/status';

const STATUS_TONE = {
  submitted: 'default', photos_checked: 'default', awaiting_assessment: 'info', assessed: 'info',
  under_review: 'primary', more_info_requested: 'warning', decided: 'success', settled: 'success',
};

// Staff see the staff label; claimants see the claimant label (contract 2.2)
export function StatusBadge({ status, audience = 'staff' }) {
  if (!status) return null;
  return <Chip size="small" color={STATUS_TONE[status] ?? 'default'} variant="outlined"
               label={statusLabel(status, audience)} sx={{ fontWeight: 600 }} />;
}

// Staff only
export function RiskBadge({ level, fraud }) {
  if (!level) return <Chip size="small" label="Checks pending" variant="outlined" />;
  const r = riskColours[level];
  return (
    <Box sx={{ display: 'inline-flex', gap: 0.75, flexWrap: 'wrap' }}>
      <Chip size="small" label={r.label} sx={{ bgcolor: r.bg, color: r.main, fontWeight: 600 }} />
      {fraud && <Chip size="small" label="Fraud flag" sx={{ bgcolor: riskColours.high.main, color: '#fff', fontWeight: 600 }} />}
    </Box>
  );
}

// A vertical list of status changes with local times.
// items: [{ status, label, at }] (claimant timeline) or history rows [{ to, by, at, note }]
export function Timeline({ items, audience = 'staff' }) {
  if (!items?.length) return <Typography variant="body2" color="text.secondary">No updates yet.</Typography>;
  return (
    <Box component="ol" sx={{ listStyle: 'none', m: 0, p: 0 }}>
      {items.map((item, i) => {
        const status = item.status ?? item.to;
        const last = i === items.length - 1;
        return (
          <Box component="li" key={`${status}-${item.at}-${i}`} sx={{ display: 'flex', gap: 1.5 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <Box sx={{ width: 12, height: 12, mt: 0.5, borderRadius: '50%', bgcolor: last ? 'primary.main' : 'divider',
                         border: 2, borderColor: last ? 'primary.main' : 'text.secondary' }} />
              {!last && <Box sx={{ width: 2, flexGrow: 1, bgcolor: 'divider', my: 0.5 }} />}
            </Box>
            <Box sx={{ pb: last ? 0 : 2 }}>
              <Typography sx={{ fontWeight: 600 }}>{item.label ?? statusLabel(status, audience)}</Typography>
              <Typography variant="body2" color="text.secondary">
                {formatDateTime(item.at)}{item.by ? ` · ${item.by}` : ''}
              </Typography>
              {item.note && <Typography variant="body2" sx={{ mt: 0.25 }}>{item.note}</Typography>}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}

// Shows `detail` from any error (contract 2.7)
export function ErrorBox({ error, sx }) {
  if (!error) return null;
  return <Alert severity="error" sx={{ mb: 2, ...sx }}>{typeof error === 'string' ? error : errorText(error)}</Alert>;
}

export function PageTitle({ title, subtitle, action }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap', mb: 3 }}>
      <Box>
        <Typography variant="h4" component="h1">{title}</Typography>
        {subtitle && <Typography color="text.secondary" sx={{ mt: 0.5 }}>{subtitle}</Typography>}
      </Box>
      {action}
    </Box>
  );
}

export function Section({ title, children, sx }) {
  return (
    <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3, ...sx }}>
      {title && <Typography variant="h6" component="h2" sx={{ mb: 2 }}>{title}</Typography>}
      {children}
    </Paper>
  );
}

// Label / value pairs in a responsive grid
export function Facts({ rows }) {
  return (
    <Box component="dl" sx={{ m: 0, display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 2 }}>
      {rows.filter(Boolean).map(([label, value]) => (
        <Box key={label}>
          <Typography component="dt" variant="body2" color="text.secondary">{label}</Typography>
          <Typography component="dd" sx={{ m: 0, fontWeight: 500, overflowWrap: 'anywhere' }}>{value ?? '–'}</Typography>
        </Box>
      ))}
    </Box>
  );
}

export function Loading() {
  return (
    <Box aria-busy="true">
      <Skeleton variant="text" width="40%" height={48} />
      <Skeleton variant="rounded" height={140} sx={{ my: 2 }} />
      <Skeleton variant="rounded" height={220} />
    </Box>
  );
}

export function Empty({ children }) {
  return (
    <Paper sx={{ p: 4, textAlign: 'center' }}>
      <Typography color="text.secondary">{children}</Typography>
    </Paper>
  );
}
