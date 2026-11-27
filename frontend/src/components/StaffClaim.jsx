// Pieces of the claim view shared by the assessor and insurer pages. Staff only: never use on claimant pages.
import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Box, ButtonBase, Link, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material';
import { assetUrl } from '../api';
import { risk as riskColours } from '../theme';
import { capitalise, formatDate, formatDateTime, money } from '../utils/format';
import { moduleInfo } from '../utils/modules';
import { riskLevel } from '../utils/risk';
import { OUTCOMES } from '../utils/status';
import PhotoViewer from './PhotoViewer';
import SafeImage from './SafeImage';
import { Facts, RiskBadge, Section, StatusBadge } from './shared';

const pct = (score) => (score == null ? '–' : Math.round(score * 100));

export function RiskSummary({ claim }) {
  const r = riskColours[claim.risk_level];
  return (
    <Section title="Photo checks">
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <Box sx={{ minWidth: 120 }}>
          <Typography sx={{ fontSize: '2.5rem', fontWeight: 700, lineHeight: 1, color: r?.main ?? 'text.secondary' }}>
            {pct(claim.risk_score)}
          </Typography>
          <Typography variant="caption" color="text.secondary">Risk score out of 100</Typography>
          <Box sx={{ mt: 1 }}><RiskBadge level={claim.risk_level} fraud={claim.fraud_flag} /></Box>
        </Box>
        <Box sx={{ flex: 1, minWidth: 220 }}>
          <Typography sx={{ fontWeight: 600, mb: 0.5 }}>Reasons</Typography>
          {claim.reasons?.length ? (
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {claim.reasons.map((reason) => <li key={reason}><Typography variant="body2">{reason}</Typography></li>)}
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {claim.risk_level ? 'No warning signs were found in any photo.' : 'The photo checks have not finished yet.'}
            </Typography>
          )}
        </Box>
      </Box>
    </Section>
  );
}

// Photos with heatmaps and every check's score
export function PhotoEvidence({ images }) {
  const sorted = [...(images ?? [])].sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1));
  const [selected, setSelected] = useState(0);
  if (!sorted.length) return <Section title="Photos"><Typography color="text.secondary">No photos uploaded.</Typography></Section>;
  const img = sorted[Math.min(selected, sorted.length - 1)];

  return (
    <Section title={`Photos (${sorted.length})`}>
      {sorted.length > 1 && (
        <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
          {sorted.map((p, i) => (
            <ButtonBase key={p.image_id} onClick={() => setSelected(i)} aria-label={`Photo ${p.image_id}`}
                        aria-pressed={i === selected}
                        sx={{ width: 96, borderRadius: 1, overflow: 'hidden', border: 2,
                              borderColor: i === selected ? 'primary.main' : 'divider', flexDirection: 'column' }}>
              <SafeImage src={assetUrl(p.url)} alt={`Photo ${p.image_id}`} sx={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', display: 'block' }} />
              <Box sx={{ width: '100%', py: 0.25, fontSize: '0.75rem', fontWeight: 600,
                         bgcolor: riskColours[p.risk_level]?.bg ?? 'background.default', color: riskColours[p.risk_level]?.main ?? 'text.secondary' }}>
                {p.risk_level ? riskColours[p.risk_level].label : 'Pending'}
              </Box>
            </ButtonBase>
          ))}
        </Box>
      )}
      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', md: '3fr 2fr' }, alignItems: 'start' }}>
        <PhotoViewer key={img.image_id} imageUrl={img.url} modules={img.modules ?? []} />
        <Box>
          <Typography sx={{ fontWeight: 600, mb: 1 }}>
            Photo {img.image_id}: {img.risk_level ? `${riskColours[img.risk_level].label} (${pct(img.risk_score)})` : 'checks pending'}
          </Typography>
          {img.duplicate_of && (
            <Typography variant="body2" color="error" sx={{ mb: 1 }}>Identical to an earlier upload (photo {img.duplicate_of})</Typography>
          )}
          {(img.modules ?? []).map((m) => {
            const level = riskLevel(m.score);
            return (
              <Box key={m.module} sx={{ py: 1, borderTop: 1, borderColor: 'divider' }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>{moduleInfo(m.module).label}</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, color: riskColours[level]?.main }}>{pct(m.score)}</Typography>
                </Box>
                {m.flags?.map((f) => <Typography key={f} variant="body2" color="text.secondary">{f}</Typography>)}
              </Box>
            );
          })}
        </Box>
      </Box>
    </Section>
  );
}

// Claim and incident details, vehicle and claimant
export function ClaimFacts({ claim }) {
  return (
    <Section title="Claim and incident">
      <Facts rows={[
        ['Claimant', `${claim.claimant.name} (${claim.claimant.email})`],
        ['Vehicle', `${claim.vehicle.registration} · ${claim.vehicle.make} ${claim.vehicle.model} (${claim.vehicle.year})`],
        ['Submitted', formatDateTime(claim.created_at)],
        ['Incident date', formatDate(claim.incident_date)],
        ['Time', claim.incident_time],
        ['Location', claim.location],
        ['Severity', capitalise(claim.severity)],
        ['Assessor', claim.assessor ?? 'Not assigned yet'],
      ]} />
      <Typography sx={{ mt: 2 }}><Box component="span" sx={{ color: 'text.secondary' }}>Description: </Box>{claim.description}</Typography>
      {claim.info_request && (
        <Typography sx={{ mt: 1 }}><Box component="span" sx={{ color: 'text.secondary' }}>Latest info request: </Box>{claim.info_request}</Typography>
      )}
    </Section>
  );
}

// Other claims by this claimant or on this vehicle, with approved amounts, and how many
// approved claims fall in the 12 months before this incident (these reduce the suggested payout).
export function PreviousClaims({ claims, recent, linkBase }) {
  const recentIds = new Set((recent ?? []).map((c) => c.id));
  const recentTotal = (recent ?? []).reduce((sum, c) => sum + (c.approved_amount ?? 0), 0);
  return (
    <Section title="Vehicle and claimant history">
      {recent?.length ? (
        <Typography sx={{ mb: 2 }}>
          <Box component="span" sx={{ fontWeight: 700 }}>{recent.length} approved claim{recent.length === 1 ? '' : 's'}</Box>
          {' '}in the 12 months before this incident, {money(recentTotal)} paid in total.
        </Typography>
      ) : (
        <Typography color="text.secondary" sx={{ mb: claims?.length ? 2 : 0 }}>
          No approved claims in the 12 months before this incident.
        </Typography>
      )}
      {!claims?.length ? (
        <Typography color="text.secondary">No other claims by this claimant or on this vehicle.</Typography>
      ) : (
        <Box sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow><TableCell>Claim</TableCell><TableCell>Vehicle</TableCell><TableCell>Incident</TableCell>
                <TableCell>Status</TableCell><TableCell>Decision</TableCell><TableCell align="right">Approved</TableCell></TableRow>
            </TableHead>
            <TableBody>
              {claims.map((c) => (
                <TableRow key={c.id} sx={recentIds.has(c.id) ? { bgcolor: 'action.hover' } : undefined}>
                  <TableCell>{linkBase ? <Link component={RouterLink} to={`${linkBase}/${c.id}`}>#{c.id}</Link> : `#${c.id}`}</TableCell>
                  <TableCell>{c.registration}{c.same_vehicle ? ' (same vehicle)' : ''}</TableCell>
                  <TableCell>{formatDate(c.incident_date)}{recentIds.has(c.id) ? ' · last 12 months' : ''}</TableCell>
                  <TableCell><StatusBadge status={c.status} /></TableCell>
                  <TableCell>{c.decision ? (OUTCOMES[c.decision] ?? capitalise(c.decision)) : '–'}</TableCell>
                  <TableCell align="right">{c.approved_amount != null ? money(c.approved_amount) : '–'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
    </Section>
  );
}

export function QuotationTable({ quotation }) {
  return (
    <Box sx={{ overflowX: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow><TableCell>Kind</TableCell><TableCell>Description</TableCell><TableCell align="right">Qty</TableCell>
            <TableCell align="right">Unit price</TableCell><TableCell align="right">Amount</TableCell></TableRow>
        </TableHead>
        <TableBody>
          {quotation.items.map((it, i) => (
            <TableRow key={i}>
              <TableCell>{capitalise(it.kind)}</TableCell>
              <TableCell>{it.description}</TableCell>
              <TableCell align="right">{it.quantity}</TableCell>
              <TableCell align="right">{money(it.unit_price)}</TableCell>
              <TableCell align="right">{money(it.amount ?? it.quantity * it.unit_price)}</TableCell>
            </TableRow>
          ))}
          <TableRow>
            <TableCell colSpan={4} sx={{ fontWeight: 700 }}>Total</TableCell>
            <TableCell align="right" sx={{ fontWeight: 700 }}>{money(quotation.total)}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
      {quotation.note && <Typography variant="body2" sx={{ mt: 1.5 }}><Box component="span" sx={{ color: 'text.secondary' }}>Note: </Box>{quotation.note}</Typography>}
      {quotation.assessor && <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>By {quotation.assessor}</Typography>}
    </Box>
  );
}
