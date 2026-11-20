import { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, Button, ButtonBase, Paper, Skeleton, Typography } from '@mui/material';
import { listClaims } from '../api/claims';
import { risk } from '../theme';

const statusText = {
  pending_review: 'Waiting for review',
  approved: 'Approved',
  escalated: 'Escalated to fraud team',
};

const columns = { xs: '72px 1fr', md: '96px 1fr 140px 190px' };

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

function ClaimRow({ claim, first }) {
  const r = risk[claim.overall_risk] ?? risk.low;
  return (
    <ButtonBase
      component={RouterLink}
      to={`/claims/${claim.id}`}
      sx={{
        position: 'relative',
        display: 'grid',
        gridTemplateColumns: columns,
        alignItems: 'center',
        columnGap: 2,
        width: '100%',
        textAlign: 'left',
        pl: 3,
        pr: 2,
        py: 2,
        borderTop: first ? 0 : 1,
        borderColor: 'divider',
        '&:hover': { bgcolor: 'action.hover' },
        '&::before': { content: '""', position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, bgcolor: r.main },
      }}
    >
      <Box>
        <Typography sx={{ fontSize: '1.75rem', fontWeight: 700, lineHeight: 1, color: r.main, fontVariantNumeric: 'tabular-nums' }}>
          {Math.round(claim.risk_score * 100)}
        </Typography>
        <Typography variant="caption" sx={{ color: r.main, fontWeight: 600 }}>{r.label}</Typography>
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontWeight: 600 }}>{claim.claimant_name}</Typography>
        <Typography variant="body2" color="text.secondary" noWrap>{claim.description}</Typography>
      </Box>
      <Typography variant="body2" sx={{ display: { xs: 'none', md: 'block' }, fontVariantNumeric: 'tabular-nums' }}>
        {formatDate(claim.incident_date)}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ display: { xs: 'none', md: 'block' } }}>
        {statusText[claim.status] ?? claim.status}
      </Typography>
    </ButtonBase>
  );
}

export default function ClaimsList() {
  const [claims, setClaims] = useState(null);

  useEffect(() => {
    listClaims().then((data) => setClaims([...data].sort((a, b) => b.risk_score - a.risk_score)));
  }, []);

  const waiting = claims?.filter((c) => c.status === 'pending_review').length ?? 0;

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1">Review queue</Typography>
          <Typography color="text.secondary">
            {claims ? `${waiting} ${waiting === 1 ? 'claim' : 'claims'} waiting for review, highest risk first` : 'Loading claims…'}
          </Typography>
        </Box>
        <Button variant="contained" component={RouterLink} to="/claims/new">New claim</Button>
      </Box>

      <Paper sx={{ overflow: 'hidden' }}>
        <Box
          sx={{
            display: { xs: 'none', md: 'grid' },
            gridTemplateColumns: columns.md,
            columnGap: 2,
            pl: 3,
            pr: 2,
            py: 1.25,
            borderBottom: 1,
            borderColor: 'divider',
            bgcolor: 'background.default',
          }}
        >
          {['Risk', 'Claim', 'Incident date', 'Status'].map((h) => (
            <Typography key={h} variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>{h}</Typography>
          ))}
        </Box>

        {claims === null &&
          [0, 1, 2].map((i) => <Skeleton key={i} variant="rectangular" height={72} sx={{ m: 2 }} />)}

        {claims?.length === 0 && (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography sx={{ mb: 2 }}>No claims yet. Create one to start a review.</Typography>
            <Button variant="outlined" component={RouterLink} to="/claims/new">New claim</Button>
          </Box>
        )}

        {claims?.map((c, i) => <ClaimRow key={c.id} claim={c} first={i === 0} />)}
      </Paper>
    </>
  );
}