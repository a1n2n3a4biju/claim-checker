import { useCallback } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, Button, Typography } from '@mui/material';
import { getMyPolicies } from '../../api';
import { Empty, ErrorBox, Facts, Loading, PageTitle, Section } from '../../components/shared';
import { formatDate, money } from '../../utils/format';
import useLoad from '../../utils/useLoad';

// My policies (number, dates, sum insured) and vehicles. Calls GET /me/policies.
export default function Dashboard() {
  const { data: policies, error, loading } = useLoad(useCallback(() => getMyPolicies(), []));

  return (
    <>
      <PageTitle title="My policies" subtitle="Your cover and the vehicles on it"
                 action={<Button variant="contained" component={RouterLink} to="/my/claims/new">Submit a claim</Button>} />
      <ErrorBox error={error} />
      {loading && !policies && <Loading />}
      {policies?.length === 0 && <Empty>You don't have any policies yet.</Empty>}
      {policies?.map((p) => (
        <Section key={p.id} title={`Policy ${p.policy_number}`}>
          <Facts rows={[
            ['Valid from', formatDate(p.start_date)],
            ['Valid until', formatDate(p.end_date)],
            ['Sum insured', money(p.sum_insured)],
            ['Premium', money(p.premium)],
            ['Deductible', money(p.deductible)],
          ]} />
          <Typography sx={{ fontWeight: 600, mt: 3, mb: 1 }}>Vehicles</Typography>
          <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' } }}>
            {p.vehicles.map((v) => (
              <Box key={v.id} sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 2 }}>
                <Typography sx={{ fontWeight: 700, letterSpacing: '0.03em' }}>{v.registration}</Typography>
                <Typography variant="body2" color="text.secondary">{v.make} {v.model}, {v.year}</Typography>
              </Box>
            ))}
          </Box>
        </Section>
      ))}
    </>
  );
}
