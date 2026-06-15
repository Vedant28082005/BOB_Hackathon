import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Shield, Activity, FileText, LogOut } from 'lucide-react'
import MetricsDashboard from './components/MetricsDashboard'
import OnboardingForm from './components/OnboardingForm'
import AssessmentPipeline from './components/AssessmentPipeline'
import ResultView from './components/ResultView'
import AuditLog from './components/AuditLog'
import LoginPage from './components/LoginPage'
import { clearAuthToken } from './api/client'
import type { AssessmentResult } from './types'

type Page = 'dashboard' | 'form' | 'pipeline' | 'result' | 'audit'

interface PipelineProgress {
  stage: string
  pct: number
}

export default function App() {
  const [authed, setAuthed] = useState(() => !!localStorage.getItem('tl_token'))
  const [role, setRole] = useState('')
  const [page, setPage] = useState<Page>('dashboard')
  const [result, setResult] = useState<AssessmentResult | null>(null)
  const [progress, setProgress] = useState<PipelineProgress>({ stage: 'QUEUED', pct: 0 })

  if (!authed) {
    return <LoginPage onLogin={(r) => { setRole(r); setAuthed(true) }} />
  }

  const handleLogout = () => { clearAuthToken(); setAuthed(false); setRole('') }

  const handleResult = (r: AssessmentResult) => {
    setResult(r)
    setPage('result')
  }

  // Called by OnboardingForm as SSE events arrive — switches to pipeline view
  const handleProgress = (stage: string, pct: number) => {
    setProgress({ stage, pct })
    if (page !== 'pipeline') setPage('pipeline')
  }

  return (
    <div className="min-h-screen bg-[#0f1117]">
      {/* Top nav */}
      <nav className="border-b border-slate-800/60 px-6 py-3 flex items-center gap-4 sticky top-0 z-40 bg-[#0f1117]/90 backdrop-blur">
        <button onClick={() => setPage('dashboard')} className="flex items-center gap-2 group">
          <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center">
            <Shield size={12} className="text-white" />
          </div>
          <span className="text-sm font-bold text-white group-hover:text-blue-300 transition-colors">TrustLayer</span>
        </button>
        <span className="text-slate-700">|</span>
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Identity Trust Framework</span>

        <div className="ml-auto flex items-center gap-2">
          {role && <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-2 py-1 rounded">{role}</span>}
          <button
            onClick={() => setPage('audit')}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors ${
              page === 'audit' ? 'text-blue-400 bg-blue-950/40' : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <FileText size={12} />Audit Log
          </button>
          {result && (
            <button
              onClick={() => setPage('result')}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                page === 'result' ? 'text-blue-400 bg-blue-950/40' : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Activity size={12} />Last Assessment
            </button>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-950/20 transition-colors"
          >
            <LogOut size={12} />Sign out
          </button>
        </div>
      </nav>

      {/* Main */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={page}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.1 }}
          style={{ minHeight: '100vh' }}
        >
          {page === 'dashboard' && (
            <MetricsDashboard onStart={() => setPage('form')} />
          )}
          {page === 'form' && (
            <OnboardingForm
              onResult={handleResult}
              onProgress={handleProgress}
              onBack={() => setPage('dashboard')}
            />
          )}
          {page === 'pipeline' && (
            <AssessmentPipeline
              stage={progress.stage}
              pct={progress.pct}
              result={result}
              onComplete={() => result && setPage('result')}
            />
          )}
          {page === 'result' && result && (
            <ResultView
              result={result}
              onBack={() => setPage('dashboard')}
            />
          )}
          {page === 'audit' && (
            <AuditLog onBack={() => setPage('dashboard')} />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
