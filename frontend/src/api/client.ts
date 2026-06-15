import type { AssessmentResult, MetricsData, BehaviouralSignals, DeviceSignals, Scenario } from '../types'

const BASE = '/api'

// ── Auth token management ─────────────────────────────────────────────────────
let _token: string | null = localStorage.getItem('tl_token')
let _onUnauthorized: (() => void) | null = null

export function setAuthToken(token: string) {
  _token = token
  localStorage.setItem('tl_token', token)
  // Store expiry time (55 min to give buffer before 60 min server expiry)
  const expiry = Date.now() + 55 * 60 * 1000
  localStorage.setItem('tl_token_expiry', String(expiry))
}

export function clearAuthToken() {
  _token = null
  localStorage.removeItem('tl_token')
  localStorage.removeItem('tl_token_expiry')
}

export function isTokenExpired(): boolean {
  const expiry = localStorage.getItem('tl_token_expiry')
  if (!expiry) return true
  return Date.now() > Number(expiry)
}

/** Register a callback to fire when any authenticated request returns 401. */
export function onUnauthorized(cb: () => void) {
  _onUnauthorized = cb
}

function _authHeaders(): Record<string, string> {
  return _token ? { Authorization: `Bearer ${_token}` } : {}
}

async function _authedFetch(url: string, opts: RequestInit = {}): Promise<Response> {
  // Proactively log out if token is already expired
  if (_token && isTokenExpired()) {
    clearAuthToken()
    _onUnauthorized?.()
    throw new Error('Session expired — please log in again')
  }
  const resp = await fetch(url, opts)
  if (resp.status === 401) {
    clearAuthToken()
    _onUnauthorized?.()
    throw new Error('Session expired — please log in again')
  }
  return resp
}

// ── Login ─────────────────────────────────────────────────────────────────────
export async function login(email: string, password: string): Promise<{ access_token: string; role: string }> {
  const form = new URLSearchParams({ username: email, password })
  const resp = await fetch(`${BASE}/v1/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  })
  if (!resp.ok) throw new Error('Login failed')
  const data = await resp.json()
  setAuthToken(data.access_token)
  return data
}

// ── Crypto utils ──────────────────────────────────────────────────────────────
export async function hashFile(file: File): Promise<string> {
  const buf = await file.arrayBuffer()
  const hashBuf = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(hashBuf)).map(b => b.toString(16).padStart(2, '0')).join('')
}

export async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // Strip data URL prefix
      resolve(result.split(',')[1] ?? result)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// ── Device fingerprint ────────────────────────────────────────────────────────
export async function getDeviceFingerprint(): Promise<string> {
  const components = [
    navigator.userAgent,
    navigator.platform,
    navigator.language,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    `${screen.width}x${screen.height}`,
    screen.colorDepth.toString(),
    navigator.hardwareConcurrency?.toString() ?? '0',
    (navigator as any).deviceMemory?.toString() ?? '0',
  ]
  const raw = components.join('|')
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw))
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
}

export function getDeviceSignals(fingerprint: string): DeviceSignals {
  return {
    device_fingerprint: fingerprint,
    user_agent: navigator.userAgent,
    platform: navigator.platform,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
    screen_resolution: `${screen.width}x${screen.height}`,
    color_depth: screen.colorDepth,
  }
}

// ── Submit assessment (async — returns job_id) ────────────────────────────────
export interface SubmitPayload {
  full_name: string
  email: string
  phone: string
  dob: string
  address: string
  pan_number: string
  doc_type: string
  doc_name_on_doc?: string
  doc_image_b64?: string    // base64 of document (or empty for demo)
  selfie_b64?: string       // base64 of selfie
  video_frames_b64?: string[]
  device: DeviceSignals
  behavioural: BehaviouralSignals
  scenario?: string
}

export async function submitAssessment(payload: SubmitPayload): Promise<{ job_id: string }> {
  const resp = await _authedFetch(`${BASE}/v1/assessments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ..._authHeaders() },
    body: JSON.stringify(payload),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? 'Submission failed')
  }
  return resp.json()
}

// ── Poll job status ───────────────────────────────────────────────────────────
export interface JobStatus {
  stage: string
  pct: number
  detail?: string
}

export async function pollJobStatus(jobId: string): Promise<JobStatus> {
  const resp = await _authedFetch(`${BASE}/v1/assessments/${jobId}/status`, {
    headers: _authHeaders(),
  })
  if (!resp.ok) throw new Error('Status poll failed')
  return resp.json()
}

// ── SSE stream for live pipeline progress ─────────────────────────────────────
export function streamProgress(
  jobId: string,
  onProgress: (status: JobStatus) => void,
  onDone: () => void,
): () => void {
  const url = `${BASE}/v1/assessments/${jobId}/stream`
  const es = new EventSource(url + `?token=${_token ?? ''}`)

  es.onmessage = (e) => {
    const data: JobStatus = JSON.parse(e.data)
    onProgress(data)
    if (data.pct >= 100) {
      es.close()
      onDone()
    }
  }

  es.onerror = () => {
    es.close()
    onDone()
  }

  return () => es.close()
}

// ── Get result ────────────────────────────────────────────────────────────────
export async function getAssessmentResult(jobId: string): Promise<AssessmentResult> {
  const resp = await _authedFetch(`${BASE}/v1/assessments/${jobId}/result`, {
    headers: _authHeaders(),
  })
  if (!resp.ok) throw new Error('Result fetch failed')
  const data = await resp.json()
  // Treat any non-SUCCESS state as not-ready — the Celery result backend may
  // not have committed the result yet even after the progress SSE fires 100%.
  if (data.status !== 'SUCCESS') throw new Error('PENDING')
  return data as AssessmentResult
}

// ── Wait for result with polling fallback ─────────────────────────────────────
export async function waitForResult(
  jobId: string,
  onProgress?: (stage: string, pct: number) => void,
  maxWaitMs = 120_000,
): Promise<AssessmentResult> {
  return new Promise((resolve, reject) => {
    let done = false
    let timeoutId: ReturnType<typeof setTimeout>
    let sseCleanup: (() => void) | null = null
    let pollInterval: ReturnType<typeof setInterval> | null = null

    const finish = (fn: () => void) => {
      if (done) return
      done = true
      clearTimeout(timeoutId)
      sseCleanup?.()
      if (pollInterval) clearInterval(pollInterval)
      fn()
    }

    // Poll job status every 2s regardless — progress display + result detection
    let lastPct = 0
    pollInterval = setInterval(async () => {
      try {
        const status = await pollJobStatus(jobId)
        if (status.pct > lastPct) {
          lastPct = status.pct
          onProgress?.(status.stage, status.pct)
        }
        if (status.pct >= 100 || status.stage === 'COMPLETE' || status.stage === 'FAILED') {
          clearInterval(pollInterval!)
          pollInterval = null
          // Fetch result
          for (let i = 0; i < 20; i++) {
            try {
              const result = await getAssessmentResult(jobId)
              finish(() => resolve(result))
              return
            } catch (e) {
              if ((e as Error).message === 'PENDING') {
                await new Promise(r => setTimeout(r, 1000))
                continue
              }
              finish(() => reject(e))
              return
            }
          }
          finish(() => reject(new Error('Result not available')))
        }
      } catch (_) {
        // polling error — keep trying
      }
    }, 2000)

    // SSE for faster updates (may fail on some proxies — polling is the fallback)
    sseCleanup = streamProgress(
      jobId,
      (status) => {
        onProgress?.(status.stage, status.pct)
        lastPct = Math.max(lastPct, status.pct)
      },
      async () => {
        // SSE signalled done — stop poll interval and fetch result
        if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
        for (let i = 0; i < 20; i++) {
          try {
            const result = await getAssessmentResult(jobId)
            finish(() => resolve(result))
            return
          } catch (e) {
            if ((e as Error).message === 'PENDING') {
              await new Promise(r => setTimeout(r, 1000))
              continue
            }
            finish(() => reject(e))
            return
          }
        }
        finish(() => reject(new Error('Result not available')))
      },
    )

    timeoutId = setTimeout(() => {
      finish(() => reject(new Error('Assessment timed out after 2 minutes')))
    }, maxWaitMs)
  })
}

// ── Other endpoints ───────────────────────────────────────────────────────────
export async function fetchMetrics(): Promise<MetricsData> {
  const resp = await _authedFetch(`${BASE}/v1/metrics`, { headers: _authHeaders() })
  if (!resp.ok) throw new Error('Metrics fetch failed')
  return resp.json()
}

export async function fetchAuditLog(limit = 50): Promise<{ entries: unknown[] }> {
  const resp = await _authedFetch(`${BASE}/v1/audit?limit=${limit}`, { headers: _authHeaders() })
  if (!resp.ok) throw new Error('Audit fetch failed')
  return resp.json()
}

// ── Demo control: wipe the identity graph (analyst/admin only) ─────────────────
export async function resetIdentityGraph(): Promise<{ nodes_removed: number }> {
  const resp = await _authedFetch(`${BASE}/v1/admin/graph/reset`, {
    method: 'POST',
    headers: _authHeaders(),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? 'Reset failed')
  }
  return resp.json()
}
