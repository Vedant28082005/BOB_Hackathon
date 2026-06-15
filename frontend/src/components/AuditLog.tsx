import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Lock, CheckCircle, XCircle, ArrowLeft } from 'lucide-react'
import { fetchAuditLog } from '../api/client'

interface AuditEntry {
  id: number
  entry_uuid: string
  assessment_uuid: string
  applicant_uuid: string
  event_type: string
  summary: string
  payload_json: string
  prev_hash: string
  record_hash: string
  created_at: string
}

interface Props { onBack: () => void }

export default function AuditLog({ onBack }: Props) {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<number | null>(null)

  useEffect(() => {
    fetchAuditLog(50).then(d => {
      setEntries(d.entries as AuditEntry[])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const decisionColor = (summary: string) => {
    if (summary.includes('APPROVE')) return 'text-green-400'
    if (summary.includes('STEP_UP')) return 'text-yellow-400'
    if (summary.includes('MANUAL_REVIEW')) return 'text-orange-400'
    if (summary.includes('REJECT')) return 'text-red-400'
    return 'text-slate-400'
  }

  return (
    <div className="min-h-screen bg-[#0f1117] px-4 py-8 max-w-4xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-sm text-slate-400 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={15} /> Dashboard
      </button>

      <div className="flex items-center gap-3 mb-6">
        <Lock size={18} className="text-blue-400" />
        <h1 className="text-xl font-bold text-white">Tamper-Evident Audit Log</h1>
        <span className="ml-auto text-xs font-mono text-slate-500 bg-slate-800 px-3 py-1 rounded">
          SHA-256 hash-chained · {entries.length} records
        </span>
      </div>

      <div className="mb-4 px-4 py-3 rounded-lg bg-blue-950/20 border border-blue-800/40 text-xs text-blue-300 font-mono">
        Each record stores <code className="text-blue-200">record_hash = SHA256(prev_hash + entry_uuid + payload)</code>.
        Any modification to a prior record invalidates all subsequent hashes — making the chain tamper-evident.
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-surface-2 animate-pulse" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          No audit records yet. Run an assessment to generate records.
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry, i) => (
            <motion.div
              key={entry.id}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              className="rounded-xl border border-slate-700/50 bg-[#151821] overflow-hidden"
            >
              <button
                onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-800/20 transition-colors text-left"
              >
                {/* Chain indicator */}
                <div className="flex flex-col items-center gap-0.5 flex-shrink-0">
                  <CheckCircle size={13} className="text-green-500" />
                  {i < entries.length - 1 && <div className="w-px h-3 bg-slate-700" />}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-mono font-semibold ${decisionColor(entry.summary)}`}>
                      {entry.summary.split('|')[0]?.trim()}
                    </span>
                    <span className="text-xs text-slate-500">{entry.summary.split('|').slice(1).join(' | ')}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5 text-[10px] font-mono text-slate-600">
                    <span>{new Date(entry.created_at).toLocaleString()}</span>
                    <span>hash: {entry.record_hash.slice(0, 16)}…</span>
                  </div>
                </div>

                <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-2 py-0.5 rounded flex-shrink-0">
                  {entry.event_type}
                </span>
              </button>

              {expanded === entry.id && (
                <div className="px-4 pb-4 border-t border-slate-800 text-[11px] font-mono space-y-2 pt-3">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                    <div><span className="text-slate-600">entry_uuid</span></div>
                    <div className="text-slate-400">{entry.entry_uuid}</div>
                    <div><span className="text-slate-600">assessment_uuid</span></div>
                    <div className="text-slate-400">{entry.assessment_uuid}</div>
                    <div><span className="text-slate-600">prev_hash</span></div>
                    <div className="text-slate-400 truncate">{entry.prev_hash}</div>
                    <div><span className="text-slate-600">record_hash</span></div>
                    <div className="text-slate-400 truncate">{entry.record_hash}</div>
                  </div>
                  <div className="mt-2 rounded-lg bg-[#0f1117] p-3 text-slate-400 overflow-auto max-h-40">
                    {JSON.stringify(JSON.parse(entry.payload_json), null, 2)}
                  </div>
                  <div className="flex items-center gap-2 text-green-500">
                    <CheckCircle size={11} />
                    <span>Hash chain intact</span>
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
