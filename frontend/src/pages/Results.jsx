import ReviewPanel from '../components/ReviewPanel';
import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import {
  Alert, Box, Button, ButtonBase, Chip, LinearProgress, Paper, Skeleton, Typography,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { analyzeClaim, assetUrl, getResults } from '../api/claims';
import EvidenceViewer from '../components/EvidenceViewer';
import { risk } from '../theme';
import { claimStatus, riskLevel } from '../utils/risk';
import { moduleInfo } from '../utils/modules';

const notAnalyzed = { main: '#8A94A3', label: 'Not analyzed' };
const nextStep = {
  low: 'Moves to fast processing',
  medium: 'An adjuster reviews the evidence',
  high: 'Sent to the fraud team to investigate',
};

const formatDate = (iso) =>
  new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
const pct = (score) => (score == null ? '–' : Math.round(score * 100));

function RiskSummary({ data, onAnalyze, analyzing }) {
  const r = risk[data.overall_risk] ?? notAnalyzed;
  const analyzed = data.overall_risk != null;

  return (
    <Paper
      sx={{
        position: 'relative', overflow: 'hidden', mb: 3, p: 3, pl: 4,
        display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '150px 1fr' }, gap: 3,
        '&::before': { content: '""', position: 'absolute', left: 0, top: 0, bottom: 0, width: 6, bgcolor: r.main },
      }}
    >
      <Box>
        <Typography sx={{ fontSize: '3rem', fontWeight: 700, lineHeight: 1, color: r.main, fontVariantNumeric: 'tabular-nums' }}>
          {pct(data.risk_score)}
        </Typography>
        <Typography sx={{ color: r.main, fontWeight: 600 }}>{r.label}</Typography>
        {analyzed && <Typography variant="caption" color="text.secondary">Risk score out of 100</Typography>}
      </Box>

      <Box>
        {analyzed ? (
          <>
            <Typography variant="h6" component="p">{nextStep[data.overall_risk]}</Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>{claimStatus(data)}</Typography>
            <Typography sx={{ fontWeight: 600, mb: 0.5 }}>Why this score</Typography>
            {data.reasons.length ? (
              <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                {data.reasons.map((reason) => <li key={reason}><Typography variant="body2">{reason}</Typography></li>)}
              </Box>
            ) : (
              <Typography variant="body2">No warning signs were found in any photo.</Typography>
            )}
          </>
        ) : (
          <>
            <Typography variant="h6" component="p">Not analyzed yet</Typography>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              Run the checks to get a risk score and evidence for each photo.
            </Typography>
            <Button variant="contained" onClick={onAnalyze} disabled={analyzing}>
              {analyzing ? 'Running checks…' : 'Run checks'}
            </Button>
            {analyzing && <LinearProgress sx={{ mt: 2, maxWidth: 320 }} />}
          </>
        )}
      </Box>
    </Paper>
  );
}

function ScoreRow({ m }) {
  const info = moduleInfo(m.module);
  const color = risk[riskLevel(m.score)]?.main ?? notAnalyzed.main;

  return (
    <Box sx={{ py: 1.5, borderTop: 1, borderColor: 'divider', '&:first-of-type': { borderTop: 0 } }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 2, alignItems: 'baseline' }}>
        <Box>
          <Typography sx={{ fontWeight: 600 }}>{info.label}</Typography>
          {info.about && <Typography variant="body2" color="text.secondary">{info.about}</Typography>}
        </Box>
        <Typography sx={{ fontWeight: 700, color, fontVariantNumeric: 'tabular-nums' }}>{pct(m.score)}</Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={(m.score ?? 0) * 100}
        aria-label={`${info.label} score`}
        sx={{ mt: 1, height: 6, borderRadius: 3, bgcolor: 'divider', '& .MuiLinearProgress-bar': { bgcolor: color } }}
      />
      {m.flags?.map((flag) => <Typography key={flag} variant="body2" sx={{ mt: 1 }}>{flag}</Typography>)}
    </Box>
  );
}

function ChecksPanel({ title, items, note }) {
  if (!items.length) return null;
  return (
    <Paper sx={{ p: 2.5, mb: 2 }}>
      <Typography variant="h6" component="h3">{title}</Typography>
      {note && <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{note}</Typography>}
      {items.map((m) => <ScoreRow key={m.module} m={m} />)}
    </Paper>
  );
}

function PhotoPicker({ images, selected, riskiestId, onSelect }) {
  if (images.length < 2) return null;
  return (
    <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mb: 2 }}>
      {images.map((img) => {
        const level = riskLevel(img.risk_score);
        const isSelected = img.image_id === selected;
        return (
          <ButtonBase
            key={img.image_id}
            onClick={() => onSelect(img.image_id)}
            aria-pressed={isSelected}
            sx={{
              flexDirection: 'column', alignItems: 'stretch', width: 132, p: 0.75, borderRadius: 1,
              border: 2, borderColor: isSelected ? 'primary.main' : 'divider', bgcolor: 'background.paper', textAlign: 'left',
            }}
          >
            <Box component="img" src={assetUrl(img.url)} alt="" sx={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', borderRadius: 0.5 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 0.75 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>Photo {img.image_id}</Typography>
              <Typography variant="body2" sx={{ fontWeight: 700, color: risk[level]?.main ?? notAnalyzed.main, fontVariantNumeric: 'tabular-nums' }}>
                {pct(img.risk_score)}
              </Typography>
            </Box>
            {img.image_id === riskiestId && <Chip label="Riskiest" size="small" color="error" variant="outlined" sx={{ mt: 0.5 }} />}
          </ButtonBase>
        );
      })}
    </Box>
  );
}

export default function Results() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);

  const load = useCallback(async () => {
    setError('');
    try {
      const d = await getResults(id);
      setData(d);
      const top = [...d.images].sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1))[0];
      setSelected(top?.image_id ?? null);
    } catch (e) {
      setError(e?.response?.data?.detail ?? e.message);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const runChecks = async () => {
    setAnalyzing(true);
    try {
      await analyzeClaim(id);
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail ?? e.message);
    } finally {
      setAnalyzing(false);
    }
  };

  if (error && !data) {
    return (
      <Alert severity="error" action={<Button color="inherit" onClick={load}>Try again</Button>}>
        The results couldn't be loaded: {error}
      </Alert>
    );
  }

  if (!data) {
    return (
      <>
        <Skeleton width={260} height={48} />
        <Skeleton variant="rectangular" height={160} sx={{ my: 3 }} />
        <Skeleton variant="rectangular" height={360} />
      </>
    );
  }

  const scored = data.images.filter((i) => i.risk_score != null);
  const riskiestId = scored.length > 1
    ? scored.reduce((a, b) => (b.risk_score > a.risk_score ? b : a)).image_id
    : null;
  const photo = data.images.find((i) => i.image_id === selected) ?? data.images[0];
  const forensic = photo?.modules.filter((m) => moduleInfo(m.module).kind === 'forensic') ?? [];
  const ai = photo?.modules.filter((m) => moduleInfo(m.module).kind === 'ai') ?? [];

  return (
    <>
      <Button component={RouterLink} to="/claims" startIcon={<ArrowBackIcon />} sx={{ mb: 2, ml: -1 }}>
        Review queue
      </Button>
      <Typography variant="h4" component="h1">{data.claimant_name}</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Claim #{data.claim_id} · Incident on {formatDate(data.incident_date)} · {data.images.length}{' '}
        {data.images.length === 1 ? 'photo' : 'photos'}
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      <RiskSummary data={data} onAnalyze={runChecks} analyzing={analyzing} />
      <ReviewPanel
        claimId={data.claim_id}
        risk={data.overall_risk}
        decision={data.reviewer_decision}
        note={data.reviewer_note}
        onSaved={load}
      />

      {photo && (
        <>
          <Typography variant="h5" component="h2" sx={{ mb: 1.5 }}>Evidence</Typography>
          <PhotoPicker images={data.images} selected={photo.image_id} riskiestId={riskiestId} onSelect={setSelected} />

          {photo.duplicate_of && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Photo {photo.image_id} is identical to an earlier upload (photo {photo.duplicate_of}).
            </Alert>
          )}

          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.4fr 1fr' }, gap: 3, alignItems: 'start' }}>
            <EvidenceViewer key={photo.image_id} imageUrl={photo.url} modules={photo.modules} />
            <Box>
              {photo.modules.length === 0 && (
                <Paper sx={{ p: 2.5 }}>
                  <Typography color="text.secondary">No check results for this photo yet.</Typography>
                </Paper>
              )}
              <ChecksPanel title="Edit checks" items={forensic} />
              <ChecksPanel
                title="AI-generation checks"
                note="Higher means the photo is more likely to be AI-generated."
                items={ai}
              />
            </Box>
          </Box>
        </>
      )}
    </>
  );
}