import { createTheme } from '@mui/material/styles';

// Risk colours are used only for risk, so colour always carries meaning.
export const risk = {
  low:    { main: '#2E7D5B', bg: '#E7F3EC', label: 'Low risk' },
  medium: { main: '#B7791F', bg: '#FBF1DE', label: 'Medium risk' },
  high:   { main: '#B3261E', bg: '#FBE7E5', label: 'High risk' },
};

const ink = '#1B2430';
const muted = '#5B6573';
const line = '#DDE2E8';
const teal = '#0E5E6F';

const theme = createTheme({
  palette: {
    primary: { main: teal },
    text: { primary: ink, secondary: muted },
    divider: line,
    background: { default: '#F3F5F7', paper: '#FFFFFF' },
    success: { main: risk.low.main },
    warning: { main: risk.medium.main },
    error: { main: risk.high.main },
  },
  typography: {
    fontFamily: '"Public Sans", "Segoe UI", system-ui, sans-serif',
    h4: { fontWeight: 700, fontSize: '1.75rem', letterSpacing: '-0.01em' },
    h5: { fontWeight: 700, fontSize: '1.375rem' },
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
  },
});

export default theme;