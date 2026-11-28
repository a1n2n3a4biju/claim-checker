// Formats from contract section 2.5, shown the way people read them.

// 45000 -> ₹45,000 (Indian digit grouping: 4,00,000)
export const money = (n) => (n == null ? '–' : `₹${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`);

// '2026-11-15' -> 15 Nov 2026 (a plain date: no time zone shift)
export function formatDate(d) {
  if (!d) return '–';
  const [y, m, day] = d.split('-').map(Number);
  return new Date(y, m - 1, day).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

// '2026-11-25T10:40:10+00:00' -> local time, e.g. 25 Nov 2026, 4:10 pm
export function formatDateTime(iso) {
  if (!iso) return '–';
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}

// Today's date as YYYY-MM-DD in local time, for date pickers
export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export const capitalise = (s) => (s ? s[0].toUpperCase() + s.slice(1).replace(/_/g, ' ') : '');
