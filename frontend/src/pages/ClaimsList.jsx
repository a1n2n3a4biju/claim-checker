import { useEffect, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import {
  Alert, Box, Button, ButtonBase, Paper, Skeleton, ToggleButton, ToggleButtonGroup, Typography,
} from '@mui/material';
import { listClaims } from '../api/claims';
import { risk, serif } from '../theme';
import { claimStatus } from '../utils/risk';

const notAnalyzed = { main: '#8A94A3', label: 'Not analyzed' };
const columns = { xs: '72px 1fr', md: '96px 1fr 150px 210px' };

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'high', label: 'High', color: risk.high.main },
  { value: 'medium', label: 'Medium', color: risk.medium.main },
  { value: 'low', label: 'Low', color: risk.low.main },
  { value: 'none', label: 'Not analyzed', color: notAnalyzed.main },
];

const countFor = (all, value) => {
  if (!all) return null;
  if (value === 'all') return all.length;
  if (value === 'none') return all.filter((c) => !c.overall_risk).length;
  return all.filter((c) => c.overall_risk === value).length;
};

const emptyText = {
  all: 'No claims yet. Create one to start a review.',
  high: 'No high-risk claims.',
  medium: 'No medium-risk claims.',
  low: 'No low-risk claims.',
  none: 'Every claim has been analyzed.',
};

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

function ClaimRow({ claim, first }) {
  const r = risk[claim.overall_risk] ?? notAnalyzed;
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
        '&:hover': { bgcolor: '#F9FAF9' },
        '&::before': { content: '""', position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, bgcolor: r.main },
      }}
    >
      <Box>
        <Typography sx={{ fontSize: '1.75rem', fontWeight: 700, lineHeight: 1, color: r.main, fontVariantNumeric: 'tabular-nums' }}>
          {claim.risk_score == null ? '–' : Math.round(claim.risk_score * 100)}
        </Typography>
        <Typography variant="caption" sx={{ color: r.main, fontWeight: 600 }}>{r.label}</Typography>
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontFamily: serif, fontWeight: 600, fontSize: '1.0625rem' }}>{claim.claimant_name}</Typography>
        <Typography variant="body2" color="text.secondary" noWrap>
          Claim #{claim.id}: {claim.description || 'no description'}
        </Typography>
      </Box>
      <Typography variant="body2" sx={{ display: { xs: 'none', md: 'block' }, fontVariantNumeric: 'tabular-nums' }}>
        {formatDate(claim.incident_date)}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ display: { xs: 'none', md: 'block' } }}>
        {claimStatus(claim)}
      </Typography>
    </ButtonBase>
  );
}

export default function ClaimsList() {
  const [params, setParams] = useSearchParams();
  const filter = FILTERS.some((f) => f.value === params.get('risk')) ? params.get('risk') : 'all';
  const [claims, setClaims] = useState(null);
  const [all, setAll] = useState(null);           // every claim, for the counts on the filter
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let ignore = false;
    listClaims().then((data) => { if (!ignore) setAll(data); }).catch(() => {});
    return () => { ignore = true; };
  }, [reload]);

  useEffect(() => {
    let ignore = false;                        // drop answers that arrive after the filter changed
    setClaims(null);
    setError('');
    const backendRisk = ['low', 'medium', 'high'].includes(filter) ? filter : undefined;
    listClaims(backendRisk)
      .then((data) => {
        if (ignore) return;
        const list = filter === 'none' ? data.filter((c) => !c.overall_risk) : data;
        setClaims([...list].sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1)));
      })
      .catch((e) => { if (!ignore) setError(e?.response?.data?.detail ?? e.message); });
    return () => { ignore = true; };
  }, [filter, reload]);

  const changeFilter = (_, value) => {
    if (!value) return;
    setParams(value === 'all' ? {} : { risk: value });
  };

  const waiting = all?.filter((c) => ['medium', 'high'].includes(c.overall_risk) && !c.reviewer_decision).length;

  return (
    <>
      <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h4" component="h1">Review queue</Typography>
          <Typography color="text.secondary">
            {waiting == null
              ? 'Loading claims…'
              : waiting === 0
                ? 'No claims are waiting for review.'
                : `${waiting} ${waiting === 1 ? 'claim is' : 'claims are'} waiting for review, highest risk first.`}
          </Typography>
        </Box>
        <Button variant="contained" component={RouterLink} to="/claims/new">New claim</Button>
      </Box>

      <ToggleButtonGroup
        value={filter}
        exclusive
        onChange={changeFilter}
        size="small"
        aria-label="Filter by risk level"
        sx={{ mb: 2, flexWrap: 'wrap', bgcolor: 'background.paper' }}
      >
        {FILTERS.map((f) => {
          const count = countFor(all, f.value);
          return (
            <ToggleButton key={f.value} value={f.value} sx={{ px: 1.75 }}>
              {f.color && <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: f.color, mr: 1 }} />}
              {f.label}
              {count != null && (
                <Box component="span" sx={{ ml: 0.75, fontWeight: 400, fontVariantNumeric: 'tabular-nums' }}>{count}</Box>
              )}
            </ToggleButton>
          );
        })}
      </ToggleButtonGroup>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" onClick={() => setReload((n) => n + 1)}>Try again</Button>}>
          The claims couldn't be loaded: {error}
        </Alert>
      )}

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

        {claims === null && !error &&
          [0, 1, 2].map((i) => <Skeleton key={i} variant="rectangular" height={72} sx={{ m: 2 }} />)}

        {claims?.length === 0 && (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography sx={{ mb: 2 }}>{emptyText[filter]}</Typography>
            {filter === 'all'
              ? <Button variant="outlined" component={RouterLink} to="/claims/new">New claim</Button>
              : <Button variant="outlined" onClick={() => setParams({})}>Show all claims</Button>}
          </Box>
        )}

        {claims?.map((c, i) => <ClaimRow key={c.id} claim={c} first={i === 0} />)}
      </Paper>
    </>
  );
}
