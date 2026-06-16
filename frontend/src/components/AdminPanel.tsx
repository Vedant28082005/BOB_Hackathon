import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowLeft, SlidersHorizontal, Save, RotateCcw, AlertTriangle, CheckCircle } from 'lucide-react'
import { getAdminConfig, updateAdminConfig, resetIdentityGraph } from '../api/client'
import type { RuntimeConfig } from '../api/client'

interface Props { onBack: () => void }

const WEIGHT_LABELS: Record<string, string> = {
  document: 'Document Forensics',
  biometric: 'Biometric Verification',
  device: 'Device & Network',
  behavioural: 'Behavioural Biometrics',
  identity_graph: 'Identity Graph',
}

const THRESHOLD_LABELS: Record<string, string> = {
  approve: 'Approve at or above',
  step_up: 'Step-up at or above',
  manual_review: 'Manual review at or above',
}

export default function AdminPanel({ onBack }: Props) {
  const [config, setConfig] = useState<RuntimeConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState('')

  useEffect(() => {
    getAdminConfig()
      .then(c => { setConfig(c); setLoading(false) })
      .catch(e => { setErr(e instanceof Error ? e.message : 'Load failed'); setLoading(false) })
  }, [])

  const weightSum = config ? Object.values(config.weights).reduce((a, b) => a + b, 0) : 0
  const weightsValid = Math.abs(weightSum - 1.0) < 0.01

  const setWeight = (k: string, v: number) =>
    setConfig(c => c ? { ...c, weights: { ...c.weights, [k]: v } } : c)
  const setThreshold = (k: string, v: number) =>
    setConfig(c => c ? { ...c, thresholds: { ...c.thresholds, [k]: v } } : c)

  const handleSave = async () => {
    if (!config) return
    setSaving(true); setMsg(''); setErr('')
    try {
      await updateAdminConfig({ weights: config.weights, thresholds: config.thresholds })
      setMsg('Configuration saved. New assessments will use these values.')
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleResetGraph = async () => {
    if (!window.confirm('Wipe the identity graph? This clears all prior test identities.')) return
    setResetting(true); setResetMsg('')
    try {
      const { nodes_removed } = await resetIdentityGraph()
      setResetMsg(`Identity graph cleared — removed ${nodes_removed} node(s).`)
    } catch (e) {
      setResetMsg(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0f1117] px-4 py-6 sm:py-8 max-w-3xl mx-auto">
      <button onClick={onBack} className="flex items-center gap-2 text-sm text-slate-400 hover:text-white mb-6 transition-colors">
        <ArrowLeft size={15} /> Dashboard
      </button>

      <div className="flex items-center gap-3 mb-2">
        <SlidersHorizontal size={18} className="text-purple-400" />
        <h1 className="text-xl font-bold text-white">Admin Console</h1>
        <span className="ml-auto text-[10px] font-mono text-purple-300 bg-purple-950/40 border border-purple-800/50 px-2 py-1 rounded">ADMIN ONLY</span>
      </div>
      <p className="text-slate-400 text-sm mb-6">Tune the fusion model weights and decision thresholds applied to every assessment.</p>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 rounded-lg bg-surface-2 animate-pulse" />)}
        </div>
      ) : err && !config ? (
        <div className="rounded-xl border border-red-800/50 bg-red-950/30 p-4 text-sm text-red-400 flex items-center gap-2">
          <AlertTriangle size={15} /> {err}
        </div>
      ) : config && (
        <div className="space-y-6">
          {/* Weights */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-slate-700/60 bg-[#151821] p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-slate-200">Fusion Weights</h2>
              <span className={`text-xs font-mono px-2 py-0.5 rounded ${weightsValid ? 'text-green-400 bg-green-950/30' : 'text-red-400 bg-red-950/30'}`}>
                Σ = {weightSum.toFixed(2)} {weightsValid ? '✓' : '(must equal 1.00)'}
              </span>
            </div>
            <div className="space-y-4">
              {Object.entries(config.weights).map(([k, v]) => (
                <div key={k}>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs text-slate-400">{WEIGHT_LABELS[k] ?? k}</label>
                    <span className="text-xs font-mono text-slate-300">{v.toFixed(2)}</span>
                  </div>
                  <input
                    type="range" min={0} max={1} step={0.05} value={v}
                    onChange={e => setWeight(k, parseFloat(e.target.value))}
                    className="w-full accent-purple-500"
                  />
                </div>
              ))}
            </div>
          </motion.div>

          {/* Thresholds */}
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
            className="rounded-xl border border-slate-700/60 bg-[#151821] p-5">
            <h2 className="text-sm font-semibold text-slate-200 mb-4">Decision Thresholds (0–100)</h2>
            <div className="space-y-3">
              {Object.entries(config.thresholds).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between gap-3">
                  <label className="text-xs text-slate-400 flex-1">{THRESHOLD_LABELS[k] ?? k}</label>
                  <input
                    type="number" min={0} max={100} value={v}
                    onChange={e => setThreshold(k, parseFloat(e.target.value) || 0)}
                    className="w-24 bg-[#0f1117] border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white text-right focus:outline-none focus:border-purple-500"
                  />
                </div>
              ))}
            </div>
          </motion.div>

          {/* Save */}
          <div>
            <button
              onClick={handleSave}
              disabled={saving || !weightsValid}
              className="w-full py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold flex items-center justify-center gap-2 transition-colors"
            >
              <Save size={14} /> {saving ? 'Saving…' : 'Save Configuration'}
            </button>
            {!weightsValid && <p className="mt-2 text-[11px] text-center text-red-400">Weights must sum to 1.00 before saving.</p>}
            {msg && <p className="mt-2 text-[11px] text-center text-green-400 flex items-center justify-center gap-1"><CheckCircle size={11} />{msg}</p>}
            {err && config && <p className="mt-2 text-[11px] text-center text-red-400">{err}</p>}
          </div>

          {/* Danger zone */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-5">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Demo Controls</h2>
            <button
              onClick={handleResetGraph}
              disabled={resetting}
              className="w-full py-2 rounded-lg border border-slate-700 hover:border-red-600/60 hover:text-red-300 disabled:opacity-50 text-slate-400 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
            >
              <RotateCcw size={12} className={resetting ? 'animate-spin' : ''} />
              {resetting ? 'Resetting…' : 'Reset Identity Graph'}
            </button>
            {resetMsg && <p className="mt-2 text-[11px] text-center text-slate-400">{resetMsg}</p>}
          </div>
        </div>
      )}
    </div>
  )
}
