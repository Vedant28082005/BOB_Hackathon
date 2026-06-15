import type { AssessmentResult, MetricsData, BehaviouralSignals, DeviceSignals, Scenario } from '../types'

const BASE = '/api'

// ── Auth token management ─────────────────────────────────────────────────────
let _token: string | null = localStorage.getItem('tl_token')

export function setAuthToken(token: string) {
  _token = token
  localStorage.setItem('tl_token', token)
}

export function clearAuthToken() {
  _token = null
  localStorage.removeItem('tl_token')
}

function _authHeaders(): Record<string, string> {
  return _token ? { Authorization: `Bearer ${_token}` } : {}
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
  const resp = await fetch(`${BASE}/v1/assessments`, {
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
  const resp = await fetch(`${BASE}/v1/assessments/${jobId}/status`, {
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
  const resp = await fetch(`${BASE}/v1/assessments/${jobId}/result`, {
    headers: _authHeaders(),
  })
  if (!resp.ok) throw new Error('Result fetch failed')
  const data = await resp.json()
  if (data.status === 'PENDING') throw new Error('PENDING')
  return data as AssessmentResult
}

// ── Wait for result with polling fallback ─────────────────────────────────────
export async function waitForResult(
  jobId: string,
  onProgress?: (stage: string, pct: number) => void,
  maxWaitMs = 120_000,
): Promise<AssessmentResult> {
  const start = Date.now()

  return new Promise((resolve, reject) => {
    const cleanup = streamProgress(
      jobId,
      (status) => onProgress?.(status.stage, status.pct),
      async () => {
        // SSE complete — fetch result
        for (let i = 0; i < 10; i++) {
          try {
            const result = await getAssessmentResult(jobId)
            resolve(result)
            return
          } catch (e) {
            if ((e as Error).message === 'PENDING') {
              await new Promise(r => setTimeout(r, 500))
              continue
            }
            reject(e)
            return
          }
        }
        reject(new Error('Result not available after pipeline completion'))
      },
    )

    // Timeout guard
    setTimeout(() => {
      cleanup()
      reject(new Error('Assessment timed out'))
    }, maxWaitMs)
  })
}

// ── Other endpoints ───────────────────────────────────────────────────────────
export async function fetchMetrics(): Promise<MetricsData> {
  const resp = await fetch(`${BASE}/v1/metrics`, { headers: _authHeaders() })
  if (!resp.ok) throw new Error('Metrics fetch failed')
  return resp.json()
}

export async function fetchAuditLog(limit = 50): Promise<{ entries: unknown[] }> {
  const resp = await fetch(`${BASE}/v1/audit?limit=${limit}`, { headers: _authHeaders() })
  if (!resp.ok) throw new Error('Audit fetch failed')
  return resp.json()
}
