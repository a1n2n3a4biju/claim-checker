import { useCallback, useState } from 'react';
import { Alert, Autocomplete, Box, Button, IconButton, MenuItem, TextField, Typography } from '@mui/material';
import DeleteIcon from '@mui/icons-material/DeleteOutlined';
import { errorText, getPriceList, submitQuotation } from '../../api';
import { money } from '../../utils/format';
import useLoad from '../../utils/useLoad';

const newRow = () => ({ key: Math.random().toString(36).slice(2), kind: 'part', description: '', quantity: 1, unit_price: '' });
const toInt = (v) => (v === '' || v == null ? NaN : Number(v));

// Rows of part or labour, description, quantity, unit price; add and remove rows; live total preview; a note.
// The price list fills a dropdown, but a custom item can still be typed. The backend calculates the real total.
export default function QuotationForm({ claimId, onSubmitted, onConflict }) {
  const { data: priceList } = useLoad(useCallback(() => getPriceList(), []));
  const [rows, setRows] = useState([newRow()]);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const update = (key, changes) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...changes } : r)));
  const amount = (r) => (Number.isInteger(toInt(r.quantity)) && Number.isInteger(toInt(r.unit_price)) ? toInt(r.quantity) * toInt(r.unit_price) : 0);
  const total = rows.reduce((sum, r) => sum + amount(r), 0);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    const bad = rows.findIndex((r) => !r.description.trim() || !(toInt(r.quantity) >= 1) || !Number.isInteger(toInt(r.quantity))
      || !(toInt(r.unit_price) >= 0) || !Number.isInteger(toInt(r.unit_price)));
    if (bad >= 0) {
      setError(`Row ${bad + 1}: enter a description, a whole-number quantity of at least 1 and a unit price in whole rupees`);
      return;
    }
    setBusy(true);
    try {
      const items = rows.map((r) => ({ kind: r.kind, description: r.description.trim(), quantity: toInt(r.quantity), unit_price: toInt(r.unit_price) }));
      onSubmitted(await submitQuotation(claimId, items, note.trim()));
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
      if (err?.status === 409) onConflict?.();
    }
  };

  return (
    <Box component="form" onSubmit={submit} noValidate>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {rows.map((r, i) => {
        const options = (priceList ?? []).filter((p) => p.kind === r.kind);
        return (
          <Box key={r.key} sx={{ display: 'grid', gap: 1.5, alignItems: 'center', mb: 1.5, pb: 1.5, borderBottom: 1, borderColor: 'divider',
                                 gridTemplateColumns: { xs: '1fr 1fr', md: '120px 1fr 90px 130px 110px 40px' } }}>
            <TextField select size="small" label="Kind" value={r.kind} disabled={busy}
                       onChange={(e) => update(r.key, { kind: e.target.value })}>
              <MenuItem value="part">Part</MenuItem>
              <MenuItem value="labour">Labour</MenuItem>
            </TextField>
            <Autocomplete
              freeSolo size="small" disabled={busy}
              options={options.map((o) => o.description)}
              inputValue={r.description}
              onInputChange={(_, value) => update(r.key, { description: value })}
              onChange={(_, value) => {
                const hit = options.find((o) => o.description === value);
                update(r.key, { description: value ?? '', ...(hit ? { unit_price: hit.unit_price } : {}) });
              }}
              renderInput={(params) => <TextField {...params} label={`Description (row ${i + 1})`} />}
              sx={{ gridColumn: { xs: '1 / -1', md: 'auto' } }}
            />
            <TextField size="small" label="Qty" type="number" value={r.quantity} disabled={busy}
                       onChange={(e) => update(r.key, { quantity: e.target.value })} slotProps={{ htmlInput: { min: 1, step: 1 } }} />
            <TextField size="small" label="Unit price (₹)" type="number" value={r.unit_price} disabled={busy}
                       onChange={(e) => update(r.key, { unit_price: e.target.value })} slotProps={{ htmlInput: { min: 0, step: 1 } }} />
            <Typography sx={{ fontWeight: 600, textAlign: { md: 'right' } }}>{money(amount(r))}</Typography>
            <IconButton aria-label={`Remove row ${i + 1}`} disabled={busy || rows.length === 1}
                        onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}>
              <DeleteIcon />
            </IconButton>
          </Box>
        );
      })}
      <Button onClick={() => setRows((rs) => [...rs, newRow()])} disabled={busy}>Add row</Button>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', my: 2 }}>
        <Typography variant="h6" component="p">Total (preview): {money(total)}</Typography>
      </Box>
      <TextField label="Note" multiline minRows={2} fullWidth value={note} onChange={(e) => setNote(e.target.value)} disabled={busy} sx={{ mb: 2 }} />
      <Button type="submit" variant="contained" disabled={busy}>{busy ? 'Submitting…' : 'Submit quotation'}</Button>
    </Box>
  );
}
