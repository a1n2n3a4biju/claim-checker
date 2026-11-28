import { useCallback } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { Alert, Button, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Link } from '@mui/material';
import { getMyClaims } from '../../api';
import { Empty, ErrorBox, Loading, PageTitle, StatusBadge } from '../../components/shared';
import { formatDate } from '../../utils/format';
import useLoad from '../../utils/useLoad';

// List of my claims, newest first: claim number, vehicle, date, status. Calls GET /me/claims.
export default function MyClaims() {
  const { data: claims, error, loading } = useLoad(useCallback(() => getMyClaims(), []));
  const { state } = useLocation();

  return (
    <>
      <PageTitle title="My claims" subtitle="Track every claim you've made"
                 action={<Button variant="contained" component={RouterLink} to="/my/claims/new">Submit a claim</Button>} />
      {state?.welcome && (
        <Alert severity="success" sx={{ mb: 3 }}>
          Your account is ready. To make a claim, your motor policy must be linked to this account; you can check it
          under My policies.
        </Alert>
      )}
      <ErrorBox error={error} />
      {loading && !claims && <Loading />}
      {claims?.length === 0 && <Empty>You haven't made any claims yet.</Empty>}
      {claims?.length > 0 && (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Claim</TableCell>
                <TableCell>Vehicle</TableCell>
                <TableCell>Incident date</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {claims.map((c) => (
                <TableRow key={c.id} hover>
                  <TableCell>
                    <Link component={RouterLink} to={`/my/claims/${c.id}`} sx={{ fontWeight: 600 }}>Claim #{c.id}</Link>
                  </TableCell>
                  <TableCell>{c.vehicle.registration}</TableCell>
                  <TableCell>{formatDate(c.incident_date)}</TableCell>
                  <TableCell><StatusBadge status={c.status} audience="claimant" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </>
  );
}
