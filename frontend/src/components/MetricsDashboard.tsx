import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Shield, CheckCircle, AlertTriangle, XCircle, Activity, Clock, TrendingUp, Users, RotateCcw } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { fetchMetrics, resetIdentityGraph } from '../api/client'
import type { MetricsData } from '../types'

interface Props { onStart: () => void }

export default function MetricsDashboard({ onStart }: Props) {
  const [metrics, setMetrics] = useState<MetricsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState('')

  const handleResetGraph = async () => {
    if (!window.confirm('Wipe the identity graph? This clears all prior test identities so your details are no longer flagged as a duplicate/ring member.')) return
    setResetting(true)
    setResetMsg('')
    try {
      const { nodes_removed } = await resetIdentityGraph()
      setResetMsg(`Identity graph cleared — removed ${nodes_removed} node(s).`)
    } catch (e) {
      setResetMsg(e instanceof Error ? e.message : 'Reset failed')
    } finally {
      setResetting(false)
    }
  }

  useEffect(() => {
    fetchMetrics().then(m => { setMetrics(m); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const cards = metrics ? [
    { label: 'Total Assessments', value: metrics.total_assessments, icon: Users, color: 'text-blue-400', bg: 'bg-blue-950/30 border-blue-800/50' },
    { label: 'Approved', value: metrics.approved, icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-950/30 border-green-800/50' },
    { label: 'Fraud Caught', value: metrics.fraud_caught, icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-950/30 border-orange-800/50' },
    { label: 'Approval Rate', value: `${metrics.approval_rate}%`, icon: TrendingUp, color: 'text-cyan-400', bg: 'bg-cyan-950/30 border-cyan-800/50' },
    { label: 'Avg Trust Score', value: metrics.avg_trust_score.toFixed(1), icon: Shield, color: 'text-purple-400', bg: 'bg-purple-950/30 border-purple-800/50' },
    { label: 'Avg Decision Time', value: `${(metrics.avg_decision_time_ms / 1000).toFixed(1)}s`, icon: Clock, color: 'text-yellow-400', bg: 'bg-yellow-950/30 border-yellow-800/50' },
    { label: 'Today', value: metrics.assessments_today, icon: Activity, color: 'text-slate-400', bg: 'bg-slate-800/30 border-slate-700/50' },
    { label: 'Manual Review', value: metrics.manual_review, icon: XCircle, color: 'text-red-400', bg: 'bg-red-950/30 border-red-800/50' },
  ] : []

  const barData = metrics ? [
    { name: 'Approved', value: metrics.approved, fill: '#22c55e' },
    { name: 'Step-Up', value: metrics.step_up, fill: '#f59e0b' },
    { name: 'Review', value: metrics.manual_review, fill: '#f97316' },
    { name: 'Rejected', value: metrics.rejected, fill: '#ef4444' },
  ] : []

  return (
    <div className="min-h-screen bg-[#0f1117] px-4 sm:px-6 py-6 sm:py-8 max-w-6xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="mb-6 sm:mb-8">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <Shield size={16} className="text-white" />
          </div>
          <span className="text-xs font-mono text-blue-400 tracking-widest uppercase">TrustLayer</span>
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-white">Identity Trust Framework</h1>
        <p className="text-slate-400 text-xs sm:text-sm mt-1">
          Privacy-first KYC risk-decisioning platform · Bank of Baroda Hackathon 2024
        </p>
      </motion.div>

      {/* System status bar */}
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}
        className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-6 sm:mb-8 px-3 sm:px-4 py-2.5 rounded-lg bg-surface-2 border border-slate-700/60 text-[11px] sm:text-xs font-mono"
      >
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-green-400">ALL SYSTEMS OPERATIONAL</span>
        </span>
        <span className="text-slate-700 hidden sm:inline">|</span>
        <span className="text-slate-400">Doc Forensics <span className="text-green-500">✓</span></span>
        <span className="text-slate-700 hidden sm:inline">|</span>
        <span className="text-slate-400">Biometrics <span className="text-green-500">✓</span></span>
        <span className="text-slate-700 hidden sm:inline">|</span>
        <span className="text-slate-400">Graph <span className="text-green-500">✓</span></span>
        <span className="text-slate-700 hidden sm:inline">|</span>
        <span className="text-slate-400">LLM <span className="text-yellow-500">◎</span></span>
      </motion.div>

      {/* Metric cards */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-surface-2 animate-pulse" />
          ))}
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8"
        >
          {cards.map((c, i) => (
            <motion.div
              key={c.label}
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i }}
              className={`rounded-xl border p-4 ${c.bg}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400">{c.label}</span>
                <c.icon size={14} className={c.color} />
              </div>
              <div className={`text-2xl font-bold font-mono ${c.color}`}>{c.value}</div>
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* Chart + CTA */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Decision distribution bar chart */}
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
          className="md:col-span-2 rounded-xl border border-slate-700/60 bg-surface-1 p-5"
        >
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Decision Distribution</h3>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={barData} barSize={40}>
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#1c2030', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#e2e8f0' }}
                  itemStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {barData.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-40 flex items-center justify-center text-slate-500 text-sm">
              No assessment data yet. Run your first assessment to populate metrics.
            </div>
          )}
        </motion.div>

        {/* Start assessment CTA */}
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.35 }}
          className="rounded-xl border border-blue-800/60 bg-blue-950/20 p-5 flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-lg bg-blue-600/30 border border-blue-500/40 flex items-center justify-center mb-3">
              <Shield size={20} className="text-blue-400" />
            </div>
            <h3 className="font-semibold text-white mb-1">New KYC Assessment</h3>
            <p className="text-slate-400 text-sm leading-relaxed">
              Run a full identity verification with live document forensics, biometric analysis, and graph-based fraud detection.
            </p>
          </div>
          <button
            onClick={onStart}
            className="mt-6 w-full py-3 rounded-lg bg-blue-600 hover:bg-blue-500 transition-colors text-white font-semibold text-sm"
          >
            Start Assessment →
          </button>

          {/* Demo control: reset the identity graph so re-submissions aren't
              flagged as duplicates of earlier test runs */}
          <button
            onClick={handleResetGraph}
            disabled={resetting}
            className="mt-2 w-full py-2 rounded-lg border border-slate-700 hover:border-slate-500 disabled:opacity-50 transition-colors text-slate-400 hover:text-slate-200 text-xs font-medium flex items-center justify-center gap-1.5"
          >
            <RotateCcw size={12} className={resetting ? 'animate-spin' : ''} />
            {resetting ? 'Resetting…' : 'Reset Identity Graph (demo)'}
          </button>
          {resetMsg && (
            <p className="mt-2 text-[11px] text-center text-slate-400">{resetMsg}</p>
          )}
        </motion.div>
      </div>
    </div>
  )
}
