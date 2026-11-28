import { useCallback } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Link, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import { getAssessorClaims } from '../../api';
import { Empty, ErrorBox, Loading, PageTitle, RiskBadge, StatusBadge } from '../../components/shared';
import { capitalise, formatDate } from '../../utils/format';
import useLoad from '../../utils/useLoad';

// Claims assigned to me, newest first, with status. Calls GET /assessor/claims.
export default function AssignedClaims() {
  const { data: claims, error, loading } = useLoad(useCallback(() => getAssessorClaims(), []));
  const waiting = claims?.filter((c) => c.status === 'awaiting_assessment').length ?? 0;

  return (
    <>
      <PageTitle title="Assigned claims"
                 subtitle={claims ? `${waiting} waiting for your quotation` : 'Claims assigned to you'} />
      <ErrorBox error={error} />
      {loading && !claims && <Loading />}
      {claims?.length === 0 && <Empty>No claims are assigned to you yet.</Empty>}
      {claims?.length > 0 && (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Claim</TableCell>
                <TableCell>Claimant</TableCell>
                <TableCell>Vehicle</TableCell>
                <TableCell>Incident date</TableCell>
                <TableCell>Severity</TableCell>
                <TableCell>Risk</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {claims.map((c) => (
                <TableRow key={c.id} hover>
                  <TableCell><Link component={RouterLink} to={`/assessor/claims/${c.id}`} sx={{ fontWeight: 600 }}>#{c.id}</Link></TableCell>
                  <TableCell>{c.claimant}</TableCell>
                  <TableCell>{c.vehicle.registration}</TableCell>
                  <TableCell>{formatDate(c.incident_date)}</TableCell>
                  <TableCell>{capitalise(c.severity)}</TableCell>
                  <TableCell><RiskBadge level={c.risk_level} fraud={c.fraud_flag} /></TableCell>
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
