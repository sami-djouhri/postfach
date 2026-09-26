function getBase(): string {
  const routerBase = (window as any).__ROUTER_BASE__ || '';
  return routerBase + '/api';
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const base = getBase();
  const res = await fetch(base + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    credentials: 'same-origin',
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    throw new Error('Nicht angemeldet');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
};

export function apiUrl(path: string): string {
  return getBase() + path;
}

export async function uploadFile(letterId: number, file: File): Promise<unknown> {
  const base = getBase();
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${base}/letters/${letterId}/files`, {
    method: 'POST',
    credentials: 'same-origin',
    body: formData,
  });
  if (res.status === 401) {
    throw new Error('Nicht angemeldet');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export async function voiceMemo(
  audio: Blob,
  opts?: { filename?: string; title?: string; language?: string },
): Promise<{ id: number }> {
  const base = getBase();
  const fd = new FormData();
  const fname = opts?.filename || 'memo.webm';
  fd.append('file', audio, fname);
  const qs = new URLSearchParams();
  if (opts?.title) qs.set('title', opts.title);
  if (opts?.language) qs.set('language', opts.language);
  const url = `${base}/letters/voice-memo${qs.toString() ? '?' + qs : ''}`;
  const res = await fetch(url, { method: 'POST', credentials: 'same-origin', body: fd });
  if (res.status === 401) throw new Error('Nicht angemeldet');
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || err.detail || res.statusText);
  }
  return res.json();
}


export async function quickScanMulti(files: File[], title?: string): Promise<{ id: number }> {
  const base = getBase();
  const formData = new FormData();
  for (const f of files) formData.append('files', f);
  const url = title
    ? `${base}/letters/quick-scan-multi?title=${encodeURIComponent(title)}`
    : `${base}/letters/quick-scan-multi`;
  const res = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    body: formData,
  });
  if (res.status === 401) throw new Error('Nicht angemeldet');
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}
