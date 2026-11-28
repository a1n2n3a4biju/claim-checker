// The sign-in token is kept in sessionStorage so a page refresh can restore the session
// with GET /me. It is cleared on sign-out, on a 401, or when the browser tab is closed.
const TOKEN_KEY = 'claimproof.token';

export function readToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function saveToken(token) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // storage blocked: the session lasts until the page is refreshed
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // nothing to clear
  }
}
