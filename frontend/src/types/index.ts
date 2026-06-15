export type Scenario =
  | 'genuine_user'
  | 'synthetic_identity'
  | 'deepfake_attempt'
  | 'tampered_document'
  | 'fraud_ring_member'
  | 'duplicate_identity'

export type Decision = 'APPROVE' | 'STEP_UP' | 'MANUAL_REVIEW' | 'REJECT'
export type RiskBand = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type Severity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface ReasonCode {
  code: string
  severity: Severity
  title: string
  message: string
  score_impact: number
}

export interface StageResult {
  score: number
  signals: Record<string, unknown>
  flags: string[]
}

export interface PipelineResult {
  document: StageResult
  biometric: StageResult
  device: StageResult
  behavioural: StageResult
  identity_graph: StageResult
}

export interface GraphNode {
  id: string
  label: string
  is_current: boolean
  in_fraud_ring: boolean
  scenario: string
}

export interface GraphLink {
  source: string
  target: string
  link_type: string
}

export interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
  rings: string[][]
}

export interface AssessmentResult {
  assessment_uuid: string
  applicant_uuid: string
  trust_score: number
  risk_band: RiskBand
  decision: Decision
  reason_codes: ReasonCode[]
  llm_explanation: string
  pipeline: PipelineResult
  graph_data: GraphData
  data_retained: string[]
  data_discarded: string[]
  processing_time_ms: number
}

export interface DeviceSignals {
  user_agent: string
  platform: string
  timezone: string
  language: string
  screen_resolution: string
  color_depth: number
  device_fingerprint: string
}

export interface BehaviouralSignals {
  keystroke_intervals_ms: number[]
  form_fill_duration_s: number
  paste_events: number
  focus_losses: number
}

export interface MetricsData {
  total_assessments: number
  approved: number
  step_up: number
  manual_review: number
  rejected: number
  approval_rate: number
  fraud_caught: number
  avg_decision_time_ms: number
  avg_trust_score: number
  assessments_today: number
}
