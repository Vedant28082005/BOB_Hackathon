import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Shield, CheckCircle, AlertTriangle, XCircle, Clock, ChevronDown,
  ChevronUp, Eye, EyeOff, ArrowLeft, FileText, Camera, Monitor, Activity, Network
} from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import type { AssessmentResult, ReasonCode, Severity } from '../types'
import IdentityGraph from './IdentityGraph'

interface Props {
  result: AssessmentResult
  onBack: () => void
}

const DECISION_CONFIG = {
  APPROVE:       { label: 'APPROVED',       color: 'text-green-400',  bg: 'bg-green-950/40 border-green-700',  icon: CheckCircle },
  STEP_UP:       { label: 'STEP-UP',        color: 'text-yellow-400', bg: 'bg-yellow-950/40 border-yellow-700', icon: AlertTriangle },
  MANUAL_REVIEW: { label: 'MANUAL REVIEW',  color: 'text-orange-400', bg: 'bg-orange-950/40 border-orange-700', icon: AlertTriangle },
  REJECT:        { label: 'REJECTED',       color: 'text-red-400',    bg: 'bg-red-950/40 border-red-700',      icon: XCircle },
}

const SEVERITY_CONFIG: Record<Severity, { color: string; dot: string }> = {
  INFO:     { color: 'text-slate-400', dot: 'bg-slate-500' },
  LOW:      { color: 'text-blue-400',  dot: 'bg-blue-500' },
  MEDIUM:   { color: 'text-yellow-400',dot: 'bg-yellow-500' },
  HIGH:     { color: 'text-orange-400',dot: 'bg-orange-500' },
  CRITICAL: { color: 'text-red-400',   dot: 'bg-red-500' },
}

const BAND_COLORS: Record<string, string> = {
  LOW:      '#22c55e',
  MEDIUM:   '#f59e0b',
  HIGH:     '#f97316',
  CRITICAL: '#ef4444',
}

const STAGE_ICONS = { document: FileText, biometric: Camera, device: Monitor, behavioural: Activity, identity_graph: Network }
const STAGE_LABELS: Record<string, string> = {
  document: 'Document', biometric: 'Biometric', device: 'Device', behavioural: 'Behavioural', identity_graph: 'Identity Graph'
}

function TrustGauge({ score, band }: { score: number; band: string }) {
  const color = BAND_COLORS[band] ?? '#94a3b8'
  const data = [{ value: score }, { value: 100 - score }]

  return (
    <div className="relative w-48 h-28 mx-auto">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%" cy="100%"
            startAngle={180} endAngle={0}
            innerRadius={55} outerRadius={72}
            dataKey="value"
            strokeWidth={0}
          >
            <Cell fill={color} />
            <Cell fill="#1c2030" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
        <span className="text-3xl font-bold font-mono" style={{ color }}>{score.toFixed(1)}</span>
        <span className="text-[10px] font-mono text-slate-500 tracking-widest">/100</span>
      </div>
    </div>
  )
}

function ReasonCodeCard({ rc }: { rc: ReasonCode }) {
  const [open, setOpen] = useState(false)
  const cfg = SEVERITY_CONFIG[rc.severity]
  if (rc.severity === 'INFO') return null
  return (
    <div className="rounded-lg border border-slate-700/50 bg-[#0f1117]/60 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-800/30 transition-colors"
      >
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${cfg.dot}`} />
        <span className="flex-1 text-sm text-white">{rc.title}</span>
        <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded ${cfg.color} bg-current/10`}
          style={{ backgroundColor: 'transparent' }}>{rc.severity}</span>
        {rc.score_impact !== 0 && (
          <span className="text-xs font-mono text-red-400 w-12 text-right">{rc.score_impact.toFixed(0)}</span>
        )}
        {open ? <ChevronUp size={13} className="text-slate-500" /> : <ChevronDown size={13} className="text-slate-500" />}
      </button>
      {open && (
        <div className="px-4 pb-3 text-xs text-slate-400 leading-relaxed border-t border-slate-800">
          <div className="pt-2">
            <span className="font-mono text-slate-600">[{rc.code}] </span>{rc.message}
          </div>
        </div>
      )}
    </div>
  )
}

function StageDetail({ stageKey, result }: { stageKey: string; result: AssessmentResult }) {
  const [open, setOpen] = useState(false)
  const stage = (result.pipeline as unknown as Record<string, { score: number; signals: Record<string, unknown>; flags: string[] }>)[stageKey]
  if (!stage) return null
  const Icon = STAGE_ICONS[stageKey as keyof typeof STAGE_ICONS] ?? Shield
  const color = stage.score >= 75 ? 'text-green-400' : stage.score >= 50 ? 'text-yellow-400' : 'text-red-400'

  return (
    <div className="rounded-lg border border-slate-700/50 bg-[#0f1117]/40">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-800/20 transition-colors"
      >
        <Icon size={14} className="text-slate-400 flex-shrink-0" />
        <span className="flex-1 text-sm text-slate-300 text-left">{STAGE_LABELS[stageKey]}</span>
        <span className={`text-sm font-bold font-mono ${color}`}>{stage.score.toFixed(0)}</span>
        {open ? <ChevronUp size={13} className="text-slate-500" /> : <ChevronDown size={13} className="text-slate-500" />}
      </button>
      {open && (
        <div className="px-4 pb-3 border-t border-slate-800 space-y-1">
          {Object.entries(stage.signals).map(([k, v]) => (
            <div key={k} className="flex justify-between text-[11px] py-0.5">
              <span className="text-slate-500 font-mono">{k}</span>
              <span className={`font-mono ${
                typeof v === 'boolean' ? (v ? 'text-green-400' : 'text-red-400') : 'text-slate-300'
              }`}>
                {typeof v === 'boolean' ? (v ? 'true' : 'false') :
                 typeof v === 'number' ? (v > 1 ? v.toFixed(1) : (v * 100).toFixed(1) + '%') :
                 Array.isArray(v) ? (v.length === 0 ? '[]' : v.join(', ')) :
                 String(v).slice(0, 60)}
              </span>
            </div>
          ))}
          {stage.flags.length > 0 && (
            <div className="pt-1 flex flex-wrap gap-1">
              {stage.flags.map(f => (
                <span key={f} className="text-[10px] font-mono text-orange-400 bg-orange-950/30 border border-orange-800/40 px-1.5 py-0.5 rounded">{f}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ResultView({ result, onBack }: Props) {
  const [showPrivacy, setShowPrivacy] = useState(false)
  const [activeTab, setActiveTab] = useState<'reason' | 'pipeline' | 'graph'>('reason')
  const cfg = DECISION_CONFIG[result.decision]
  const DecisionIcon = cfg.icon
  const nonInfoCodes = result.reason_codes.filter(rc => rc.severity !== 'INFO')

  return (
    <div className="min-h-screen bg-[#0f1117] px-3 sm:px-4 py-6 sm:py-8 max-w-5xl mx-auto">
      {/* Back */}
      <button onClick={onBack} className="flex items-center gap-2 text-sm text-slate-400 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={15} /> New Assessment
      </button>

      {/* Decision hero */}
      <motion.div
        initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
        className={`rounded-2xl border p-6 mb-6 ${cfg.bg}`}
      >
        <div className="flex flex-col sm:flex-row gap-4 sm:gap-6 items-start">
          {/* Score gauge */}
          <div className="text-center flex-shrink-0 w-full sm:w-auto">
            <TrustGauge score={result.trust_score} band={result.risk_band} />
            <p className="text-xs font-mono text-slate-400 mt-1">Trust Score</p>
          </div>

          {/* Decision details */}
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-3">
              <DecisionIcon size={22} className={cfg.color} />
              <h1 className={`text-2xl font-bold font-mono ${cfg.color}`}>{cfg.label}</h1>
              <span className={`ml-2 text-xs font-mono px-2 py-1 rounded-md border ${
                result.risk_band === 'LOW' ? 'text-green-400 border-green-700 bg-green-950/30' :
                result.risk_band === 'MEDIUM' ? 'text-yellow-400 border-yellow-700 bg-yellow-950/30' :
                result.risk_band === 'HIGH' ? 'text-orange-400 border-orange-700 bg-orange-950/30' :
                'text-red-400 border-red-700 bg-red-950/30'
              }`}>{result.risk_band} RISK</span>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed mb-4 border-l-2 border-slate-600 pl-3 italic">
              "{result.llm_explanation}"
            </p>

            <div className="flex flex-wrap gap-4 text-xs text-slate-400 font-mono">
              <div className="flex items-center gap-1.5"><Clock size={11} />{(result.processing_time_ms / 1000).toFixed(2)}s</div>
              <div className="flex items-center gap-1.5"><Shield size={11} />{nonInfoCodes.length} signal(s) flagged</div>
              <div className="text-slate-600">{result.assessment_uuid.slice(0, 8)}…</div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Tabs — scrollable on mobile */}
      <div className="flex gap-1 mb-4 border-b border-slate-800 pb-0 overflow-x-auto">
        {(['reason', 'pipeline', 'graph'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 sm:px-4 py-2.5 text-xs sm:text-sm font-medium whitespace-nowrap capitalize transition-colors border-b-2 -mb-px flex-shrink-0 ${
              activeTab === tab ? 'text-blue-400 border-blue-500' : 'text-slate-500 border-transparent hover:text-slate-300'
            }`}
          >
            {tab === 'reason' ? `Reason Codes (${nonInfoCodes.length})` :
             tab === 'pipeline' ? 'Pipeline Detail' : 'Identity Graph'}
          </button>
        ))}
      </div>

      {/* Reason codes tab */}
      {activeTab === 'reason' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
          {nonInfoCodes.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-sm">No risk signals detected.</div>
          ) : (
            nonInfoCodes.map(rc => <ReasonCodeCard key={rc.code} rc={rc} />)
          )}
        </motion.div>
      )}

      {/* Pipeline detail tab */}
      {activeTab === 'pipeline' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
          {Object.keys(result.pipeline).map(k => (
            <StageDetail key={k} stageKey={k} result={result} />
          ))}
        </motion.div>
      )}

      {/* Identity graph tab */}
      {activeTab === 'graph' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <IdentityGraph graphData={result.graph_data} />
        </motion.div>
      )}

      {/* Privacy / data minimization panel */}
      <div className="mt-6 rounded-xl border border-slate-700/50 bg-[#151821] overflow-hidden">
        <button
          onClick={() => setShowPrivacy(v => !v)}
          className="w-full flex items-center gap-3 px-5 py-4 hover:bg-slate-800/20 transition-colors"
        >
          {showPrivacy ? <EyeOff size={15} className="text-slate-400" /> : <Eye size={15} className="text-slate-400" />}
          <span className="text-sm font-semibold text-slate-300">Privacy & Data Minimization</span>
          <span className="ml-auto text-[10px] font-mono text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
            {result.data_retained.length} retained · {result.data_discarded.length} discarded
          </span>
          {showPrivacy ? <ChevronUp size={13} className="text-slate-500" /> : <ChevronDown size={13} className="text-slate-500" />}
        </button>

        {showPrivacy && (
          <div className="px-4 sm:px-5 pb-5 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            <div>
              <h4 className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-3 mt-4">
                ✓ Data Retained
              </h4>
              <ul className="space-y-1">
                {result.data_retained.map(item => (
                  <li key={item} className="text-[11px] text-slate-400 flex gap-2">
                    <span className="text-green-600 flex-shrink-0">·</span>{item}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-3 mt-4">
                ✗ Data Discarded
              </h4>
              <ul className="space-y-1">
                {result.data_discarded.map(item => (
                  <li key={item} className="text-[11px] text-slate-400 flex gap-2">
                    <span className="text-red-600 flex-shrink-0">·</span>{item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
