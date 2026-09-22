// API client for e-Abhilekh — built strictly against packages/contracts/CONTRACT.md.
// - Base URL from VITE_API_URL, default http://localhost:8000, prefix /api/v1
// - Attaches `Authorization: Bearer <access_token>` from localStorage
// - On 401: tries /auth/refresh once, retries the original request, else redirects to /login
// - All errors surface as ApiError carrying the contract's error envelope + X-Request-ID

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '') || 'http://localhost:8000';
export const API_PREFIX = `${BASE_URL}/api/v1`;

const ACCESS_KEY = 'eabhilekh.access_token';
const REFRESH_KEY = 'eabhilekh.refresh_token';

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}
export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string | null;

  constructor(status: number, code: string, message: string, requestId: string | null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }

  get friendly(): string {
    if (this.status === 403) return `Access denied (403). ${this.message}`;
    if (this.status === 0) return `Could not reach the API at ${BASE_URL}. Is the backend running?`;
    return `${this.message} (${this.code})`;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  query?: Record<string, string | number | boolean | undefined>;
  /** internal: skip the 401-refresh cycle (used by the refresh call itself) */
  noAuthRetry?: boolean;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(API_PREFIX + path);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function parseError(res: Response): Promise<ApiError> {
  const rid = res.headers.get('X-Request-ID');
  let code = 'UNKNOWN';
  let message = `Request failed with status ${res.status}`;
  let ridBody: string | null = null;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object' && 'error' in body) {
      const e = (body as { error: { code?: string; message?: string; request_id?: string } }).error;
      if (e.code) code = e.code;
      if (e.message) message = e.message;
      if (e.request_id) ridBody = e.request_id;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, code, message, rid ?? ridBody);
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refresh = getRefreshToken();
      if (!refresh) return false;
      try {
        const res = await fetch(`${API_PREFIX}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return false;
        const data = (await res.json()) as { access_token: string; refresh_token: string };
        if (!data.access_token) return false;
        setTokens(data.access_token, data.refresh_token ?? refresh);
        return true;
      } catch {
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

function forceLogin(): never {
  clearTokens();
  if (window.location.pathname !== '/login') {
    window.location.assign('/login');
  }
  throw new ApiError(401, 'UNAUTHENTICATED', 'Session expired — please log in again.', null);
}

async function rawRequest(path: string, opts: RequestOptions, token: string | null): Promise<Response> {
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  return fetch(buildUrl(path, opts.query), {
    method: opts.method ?? 'GET',
    headers,
    body,
  });
}

/** Core JSON request. Returns the parsed body (204 → null). */
export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  let res: Response;
  try {
    res = await rawRequest(path, opts, getAccessToken());
  } catch (e) {
    throw new ApiError(0, 'NETWORK_ERROR', e instanceof Error ? e.message : 'Network error', null);
  }

  if (res.status === 401 && !opts.noAuthRetry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return api<T>(path, { ...opts, noAuthRetry: true });
    }
    return forceLogin();
  }

  if (res.status === 401) return forceLogin();

  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return null as T;
  const text = await res.text();
  if (!text) return null as T;
  return JSON.parse(text) as T;
}

export interface BlobResult {
  blob: Blob;
  filename: string;
  requestId: string | null;
}

/** Download a binary response (documents, export ZIPs) with auth + refresh handling. */
export async function apiBlob(path: string, query?: RequestOptions['query']): Promise<BlobResult> {
  const attempt = async (token: string | null): Promise<Response> => {
    try {
      return await fetch(buildUrl(path, query), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch (e) {
      throw new ApiError(0, 'NETWORK_ERROR', e instanceof Error ? e.message : 'Network error', null);
    }
  };

  let res = await attempt(getAccessToken());
  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (!refreshed) return forceLogin();
    res = await attempt(getAccessToken());
    if (res.status === 401) return forceLogin();
  }
  if (!res.ok) throw await parseError(res);

  const blob = await res.blob();
  const cd = res.headers.get('Content-Disposition') ?? '';
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
  const filename = m ? decodeURIComponent(m[1]) : 'download';
  return { blob, filename, requestId: res.headers.get('X-Request-ID') };
}

export const apiGet = <T = unknown>(path: string, query?: RequestOptions['query']) => api<T>(path, { query });
export const apiPost = <T = unknown>(path: string, body?: unknown) => api<T>(path, { method: 'POST', body });
export const apiPostForm = <T = unknown>(path: string, form: FormData, query?: RequestOptions['query']) =>
  api<T>(path, { method: 'POST', form, query });
