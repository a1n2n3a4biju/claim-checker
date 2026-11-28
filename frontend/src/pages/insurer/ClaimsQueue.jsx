import { useCallback } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import { Box, Link, MenuItem, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField } from '@mui/material';
import { getInsurerClaims } from '../../api';
import { Empty, ErrorBox, Loading, PageTitle, RiskBadge, StatusBadge } from '../../components/shared';
import { formatDate, money } from '../../utils/format';
import { STATUSES, STATUS_KEYS } from '../../utils/status';
import useLoad from '../../utils/useLoad';

// All claims; filters for status and risk (kept in the address); fraud flags and high risk first.
// Calls GET /insurer/claims?status=&risk=
export default function ClaimsQueue() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? '';
  const risk = params.get('risk') ?? '';
  const { data: claims, error, loading } = useLoad(useCallback(() => getInsurerClaims({ status, risk }), [status, risk]));

  const setFilter = (key) => (e) => {
    const next = new URLSearchParams(params);
    if (e.target.value) next.set(key, e.target.value); else next.delete(key);
    setParams(next, { replace: true });
  };

  return (
    <>
      <PageTitle title="Claims queue" subtitle="Fraud flags and high risk first" />
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField select size="small" label="Status" value={status} onChange={setFilter('status')} sx={{ minWidth: 220 }}>
          <MenuItem value="">All statuses</MenuItem>
          {STATUS_KEYS.map((k) => <MenuItem key={k} value={k}>{STATUSES[k].staff}</MenuItem>)}
        </TextField>
        <TextField select size="small" label="Risk" value={risk} onChange={setFilter('risk')} sx={{ minWidth: 160 }}>
          <MenuItem value="">All risk levels</MenuItem>
          <MenuItem value="high">High</MenuItem>
          <MenuItem value="medium">Medium</MenuItem>
          <MenuItem value="low">Low</MenuItem>
        </TextField>
      </Box>
      <ErrorBox error={error} />
      {loading && !claims && <Loading />}
      {claims?.length === 0 && <Empty>No claims match these filters.</Empty>}
      {claims?.length > 0 && (
        <TableContainer component={Paper} sx={{ opacity: loading ? 0.6 : 1 }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Claim</TableCell>
                <TableCell>Claimant</TableCell>
                <TableCell>Vehicle</TableCell>
                <TableCell>Incident date</TableCell>
                <TableCell>Risk</TableCell>
                <TableCell>Assessor</TableCell>
                <TableCell align="right">Quotation</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {claims.map((c) => (
                <TableRow key={c.id} hover>
                  <TableCell><Link component={RouterLink} to={`/insurer/claims/${c.id}`} sx={{ fontWeight: 600 }}>#{c.id}</Link></TableCell>
                  <TableCell>{c.claimant}</TableCell>
                  <TableCell>{c.vehicle.registration}</TableCell>
                  <TableCell>{formatDate(c.incident_date)}</TableCell>
                  <TableCell><RiskBadge level={c.risk_level} fraud={c.fraud_flag} /></TableCell>
                  <TableCell>{c.assessor ?? '–'}</TableCell>
                  <TableCell align="right">{money(c.quotation_total)}</TableCell>
                  <TableCell><StatusBadge status={c.status} /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </>
  );
}
