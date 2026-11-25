import { createTheme } from '@mui/material/styles';

// Claim Checker: the claims integrity desk of an insurance firm.
// Quiet, institutional surfaces; colour is reserved for risk and for decision stamps.

export const risk = {
  low:    { main: '#2E7D5B', bg: '#E7F3EC', label: 'Low risk' },
  medium: { main: '#B7791F', bg: '#FBF1DE', label: 'Medium risk' },
  high:   { main: '#B3261E', bg: '#FBE7E5', label: 'High risk' },
};

// Ink colours for decision stamps (only used there)
export const stamp = {
  approved: '#1E6B45',
  escalated: '#8C1D18',
};

export const ink = '#1C2833';
export const firmTeal = '#0F4C5C';
export const serif = '"Source Serif 4", Georgia, "Times New Roman", serif';

const muted = '#5A6672';
const line = '#DCE0E3';

const theme = createTheme({
  palette: {
    primary: { main: firmTeal },
    text: { primary: ink, secondary: muted },
    divider: line,
    background: { default: '#F5F6F4', paper: '#FFFFFF' },
    success: { main: risk.low.main },
    warning: { main: risk.medium.main },
    error: { main: risk.high.main },
  },
  typography: {
    fontFamily: '"Public Sans", "Segoe UI", system-ui, sans-serif',
    // Page titles and claim names read like case-file headings
    h4: { fontFamily: serif, fontWeight: 600, fontSize: '2rem', lineHeight: 1.2, letterSpacing: '-0.01em' },
    h5: { fontFamily: serif, fontWeight: 600, fontSize: '1.5rem', lineHeight: 1.25 },
    h6: { fontWeight: 600, fontSize: '1.0625rem' },
    body1: { fontSize: '0.9375rem', lineHeight: 1.55 },
    body2: { fontSize: '0.875rem', lineHeight: 1.5 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  shape: { borderRadius: 6 },
  components: {
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { border: `1px solid ${line}` } },
    },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiOutlinedInput: { styleOverrides: { root: { backgroundColor: '#FFFFFF' } } },
    MuiTab: { styleOverrides: { root: { textTransform: 'none', fontWeight: 600 } } },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          color: muted,
          '&.Mui-selected': { color: ink, backgroundColor: '#E6EEF0' },
        },
      },
    },
  },
});

export default theme;
