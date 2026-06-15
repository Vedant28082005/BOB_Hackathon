import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Settings, ChevronRight } from 'lucide-react'
import type { Scenario } from '../types'

const SCENARIOS: { id: Scenario; label: string; tag: string; color: string; desc: string }[] = [
  {
    id: 'genuine_user',
    label: 'Genuine User',
    tag: 'APPROVE',
    color: 'text-green-400 border-green-700 bg-green-950/40',
    desc: 'All signals clean. High trust score. Immediate approval.',
  },
  {
    id: 'synthetic_identity',
    label: 'Synthetic Identity',
    tag: 'STEP_UP',
    color: 'text-yellow-400 border-yellow-700 bg-yellow-950/40',
    desc: 'Thin footprint, minor mismatches. Step-up verification required.',
  },
  {
    id: 'deepfake_attempt',
    label: 'Deepfake Attempt',
    tag: 'REJECT',
    color: 'text-red-400 border-red-700 bg-red-950/40',
    desc: 'Liveness failure, GAN artifacts, injection attack. Hard reject.',
  },
  {
    id: 'tampered_document',
    label: 'Tampered Document',
    tag: 'MANUAL REVIEW',
    color: 'text-orange-400 border-orange-700 bg-orange-950/40',
    desc: 'Pixel-level tampering, font substitution, name OCR mismatch.',
  },
  {
    id: 'fraud_ring_member',
    label: 'Fraud Ring Member',
    tag: 'MANUAL REVIEW',
    color: 'text-purple-400 border-purple-700 bg-purple-950/40',
    desc: 'Device fingerprint links to 5-member planted ring. Ring lights up.',
  },
  {
    id: 'duplicate_identity',
    label: 'Duplicate Identity',
    tag: 'REJECT',
    color: 'text-red-400 border-red-700 bg-red-950/40',
    desc: 'Email/phone match existing applicant. Identity reuse detected.',
  },
]

interface Props {
  scenario: Scenario
  onChange: (s: Scenario) => void
}

export default function DemoControl({ scenario, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const current = SCENARIOS.find(s => s.id === scenario) ?? SCENARIOS[0]

  return (
    <div className="fixed bottom-5 right-5 z-50">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="mb-3 w-80 rounded-xl border border-slate-700 bg-[#151821] shadow-2xl overflow-hidden"
          >
            <div className="px-4 py-3 border-b border-slate-700 flex items-center gap-2">
              <Settings size={14} className="text-slate-400" />
              <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Demo Control Panel</span>
            </div>
            <div className="p-2 space-y-1">
              {SCENARIOS.map(s => (
                <button
                  key={s.id}
                  onClick={() => { onChange(s.id); setOpen(false) }}
                  className={`w-full text-left rounded-lg px-3 py-2.5 border transition-all ${
                    s.id === scenario
                      ? s.color + ' border-opacity-100'
                      : 'border-transparent hover:bg-slate-800/60 text-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{s.label}</span>
                    <span className={`text-[10px] font-bold tracking-widest px-1.5 py-0.5 rounded ${
                      s.id === scenario ? '' : 'text-slate-500'
                    }`}>{s.tag}</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5 leading-snug">{s.desc}</p>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 rounded-full bg-[#1c2030] border border-slate-600 shadow-xl px-4 py-2.5 hover:border-blue-500 transition-all"
      >
        <Settings size={15} className="text-blue-400" />
        <span className="text-xs font-semibold text-slate-200">Demo: {current.label}</span>
        <ChevronRight size={13} className={`text-slate-500 transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
    </div>
  )
}
