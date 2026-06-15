import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Camera, Monitor, Activity, Network, CheckCircle, Clock } from 'lucide-react'
import type { AssessmentResult } from '../types'

interface Props {
  /** Current pipeline stage key received via SSE (e.g. "DOCUMENT", "BIOMETRIC") */
  stage: string
  /** Percentage completion 0-100 */
  pct: number
  /** Set once the job finishes */
  result: AssessmentResult | null
  onComplete: () => void
}

const STAGES = [
  { key: 'DOCUMENT',       label: 'Document Forensics',      Icon: FileText,  desc: 'PaddleOCR · ELA · EXIF · Aadhaar/PAN checksum' },
  { key: 'BIOMETRIC',      label: 'Biometric Verification',  Icon: Camera,    desc: 'ArcFace match · MiniFASNet liveness · EfficientNet-B4 deepfake' },
  { key: 'DEVICE',         label: 'Device & Network',        Icon: Monitor,   desc: 'Fingerprint · IP signals · GeoIP · Emulator detection' },
  { key: 'BEHAVIOURAL',    label: 'Behavioural Biometrics',  Icon: Activity,  desc: 'Keystroke cadence · Form-fill timing · Bot detection' },
  { key: 'GRAPH',          label: 'Identity Graph',          Icon: Network,   desc: 'Neo4j fraud-ring BFS · Duplicate check · Graph analysis' },
]

/** Map SSE stage names → index. Anything before "DOCUMENT" = -1 (not started). */
function stageIndex(stage: string): number {
  return STAGES.findIndex(s => s.key === stage.toUpperCase())
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 75 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
      <span className="text-xs font-mono font-bold w-10 text-right" style={{ color }}>
        {score.toFixed(0)}
      </span>
    </div>
  )
}

export default function AssessmentPipeline({ stage, pct, result, onComplete }: Props) {
  const [autoAdvanced, setAutoAdvanced] = useState(false)

  // Auto-navigate to result when result arrives and 100% reached
  useEffect(() => {
    if (result && pct >= 100 && !autoAdvanced) {
      setAutoAdvanced(true)
      const t = setTimeout(onComplete, 800)
      return () => clearTimeout(t)
    }
  }, [result, pct, autoAdvanced, onComplete])

  const currentIdx = stageIndex(stage)
  const isDone = result !== null && pct >= 100

  const stageScore = (key: string): number | null => {
    if (!result) return null
    const map: Record<string, number | undefined> = {
      DOCUMENT:    result.pipeline?.document?.score,
      BIOMETRIC:   result.pipeline?.biometric?.score,
      DEVICE:      result.pipeline?.device?.score,
      BEHAVIOURAL: result.pipeline?.behavioural?.score,
      GRAPH:       result.pipeline?.identity_graph?.score,
    }
    return map[key] ?? null
  }

  return (
    <div className="min-h-screen bg-[#0f1117] flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 bg-blue-600/10 border border-blue-600/30 rounded-full px-4 py-1.5 mb-4">
            <span className={`w-2 h-2 rounded-full ${isDone ? 'bg-green-400' : 'bg-blue-400 animate-pulse'}`} />
            <span className="text-xs font-mono text-blue-300">
              {isDone ? 'Assessment complete' : 'Assessment in progress'}
            </span>
          </div>
          <h2 className="text-xl font-bold text-white">Running KYC Pipeline</h2>
          <p className="text-sm text-slate-400 mt-1">
            {isDone
              ? `Trust score: ${result.trust_score.toFixed(0)} · ${result.decision}`
              : `${stage.replace('_', ' ')} · ${pct}% complete`}
          </p>

          {/* Progress bar */}
          <div className="mt-4 h-1 bg-slate-800 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-blue-500 rounded-full"
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.4, ease: 'easeOut' }}
            />
          </div>
          <p className="text-[10px] font-mono text-slate-600 mt-1">{pct}%</p>
        </div>

        {/* Stage cards */}
        <div className="space-y-3">
          {STAGES.map((s, i) => {
            const isActive  = i === currentIdx && !isDone
            const isComplete = isDone || i < currentIdx
            const score = stageScore(s.key)

            return (
              <motion.div
                key={s.key}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: i <= currentIdx + 1 ? 1 : 0.35, x: 0 }}
                transition={{ delay: i * 0.06 }}
                className={`rounded-xl border p-4 transition-all ${
                  isActive    ? 'border-blue-500/60 bg-blue-950/20' :
                  isComplete  ? 'border-slate-700/60 bg-[#151821]'  :
                  'border-slate-800/40 bg-[#151821]/40'
                }`}
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    isComplete ? 'bg-green-500/20 text-green-400' :
                    isActive   ? 'bg-blue-500/20 text-blue-400'   :
                    'bg-slate-800 text-slate-600'
                  }`}>
                    {isComplete
                      ? <CheckCircle size={16} />
                      : isActive
                        ? <span className="w-4 h-4 border-2 border-blue-400/40 border-t-blue-400 rounded-full animate-spin block" />
                        : <s.Icon size={16} />
                    }
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className={`text-sm font-semibold ${
                        isComplete ? 'text-white' : isActive ? 'text-blue-200' : 'text-slate-500'
                      }`}>{s.label}</span>
                      {isActive && (
                        <span className="text-[10px] font-mono text-blue-400 animate-pulse">PROCESSING</span>
                      )}
                      {isComplete && (
                        <span className="text-[10px] font-mono text-green-500">COMPLETE</span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">{s.desc}</p>
                  </div>
                </div>
                {isComplete && score !== null && (
                  <ScoreBar score={score} />
                )}
              </motion.div>
            )
          })}
        </div>

        {/* Done footer */}
        <AnimatePresence>
          {isDone && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-6 text-center"
            >
              <div className="inline-flex items-center gap-2 mb-4 text-sm text-slate-400">
                <Clock size={13} />
                Completed in {(result.processing_time_ms / 1000).toFixed(2)}s
              </div>
              <button
                onClick={onComplete}
                className="block w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all"
              >
                View Assessment Results →
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
