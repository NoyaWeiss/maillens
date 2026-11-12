// Security Console API client. Same origin as the backend; no cookies (bearer session in this tab only).
const KEY = 'maillens_session';

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

function store() {
  try { return window.sessionStorage; } catch { return null; }
}

export function getSession() {
  try { return JSON.parse(store()?.getItem(KEY) || 'null'); } catch { return null; }
}

export function clearSession() {
  try { store()?.removeItem(KEY); } catch { /* ignore */ }
}

async function request(path, { method = 'GET', body, auth = false } = {}) {
  const headers = { Accept: 'application/json' };
  if (body) headers['Content-Type'] = 'application/json';
  if (auth) {
    const s = getSession();
    if (!s) throw new ApiError(401, 'No session');
    headers.Authorization = `Bearer ${s.token}`;
  }
  let res;
  try {
    res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined, credentials: 'omit', cache: 'no-store' });
  } catch {
    throw new ApiError(0, 'The MailLens backend is unreachable.');
  }
  if (res.status === 401 && auth) clearSession();
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail || ''; } catch { /* ignore */ }
    throw new ApiError(res.status, detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** Consumes a one-time launch code from the URL fragment (then removes it from the address bar). */
export async function redeemLaunchCode() {
  const m = window.location.hash.match(/^#launch=([A-Za-z0-9_-]{20,100})$/);
  if (!m) return null;
  window.history.replaceState(null, '', window.location.pathname + '#/overview');
  const out = await request('/v1/dashboard/session', { method: 'POST', body: { code: m[1] } });
  const session = { token: out.token, context: out.context, label: out.account_label || '', expires: Date.now() + out.expires_in * 1000 };
  try { store()?.setItem(KEY, JSON.stringify(session)); } catch { /* memory only */ }
  return session;
}

export const api = {
  emails: () => request('/v1/dashboard/emails', { auth: true }),
  email: (id) => request(`/v1/dashboard/emails/${encodeURIComponent(id)}`, { auth: true }),
  clearHistory: () => request('/v1/dashboard/history', { method: 'DELETE', auth: true }),
  evaluation: () => request('/v1/dashboard/evaluation'),
};
