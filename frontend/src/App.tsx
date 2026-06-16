import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Shield, Activity, FileText, LogOut, Menu, X, SlidersHorizontal } from 'lucide-react'
import MetricsDashboard from './components/MetricsDashboard'
import OnboardingForm from './components/OnboardingForm'
import AssessmentPipeline from './components/AssessmentPipeline'
import ResultView from './components/ResultView'
import AuditLog from './components/AuditLog'
import AdminPanel from './components/AdminPanel'
import LoginPage from './components/LoginPage'
import { clearAuthToken, onUnauthorized, isTokenExpired } from './api/client'
import type { AssessmentResult } from './types'

type Page = 'dashboard' | 'form' | 'pipeline' | 'result' | 'audit' | 'admin'

interface PipelineProgress {
  stage: string
  pct: number
}

export default function App() {
  const [authed, setAuthed] = useState(() => {
    const token = localStorage.getItem('tl_token')
    if (!token) return false
    if (isTokenExpired()) { clearAuthToken(); return false }
    return true
  })
  const [role, setRole] = useState('')
  const [page, setPage] = useState<Page>('dashboard')
  const [result, setResult] = useState<AssessmentResult | null>(null)
  const [progress, setProgress] = useState<PipelineProgress>({ stage: 'QUEUED', pct: 0 })
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [sessionExpiredMsg, setSessionExpiredMsg] = useState(false)

  // Wire up global 401 handler
  useEffect(() => {
    onUnauthorized(() => {
      setSessionExpiredMsg(true)
      setAuthed(false)
      setRole('')
    })
  }, [])

  if (!authed) {
    return (
      <LoginPage
        onLogin={(r) => {
          setRole(r)
          setAuthed(true)
          setSessionExpiredMsg(false)
          // Auditors are read-only — land them directly on the audit log.
          setPage(r === 'auditor' ? 'audit' : 'dashboard')
        }}
        sessionExpired={sessionExpiredMsg}
      />
    )
  }

  const isAuditor = role === 'auditor'
  const isAdmin = role === 'admin'

  const handleLogout = () => { clearAuthToken(); setAuthed(false); setRole(''); setMobileMenuOpen(false) }

  const handleResult = (r: AssessmentResult) => {
    setResult(r)
    setPage('result')
  }

  const handleProgress = (stage: string, pct: number) => {
    setProgress({ stage, pct })
    if (page !== 'pipeline') setPage('pipeline')
  }

  const navTo = (p: Page) => { setPage(p); setMobileMenuOpen(false) }

  return (
    <div className="min-h-screen bg-[#0f1117]">
      {/* Top nav */}
      <nav className="border-b border-slate-800/60 px-4 py-3 flex items-center gap-3 sticky top-0 z-40 bg-[#0f1117]/95 backdrop-blur">
        <button onClick={() => navTo('dashboard')} className="flex items-center gap-2 group flex-shrink-0">
          <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center">
            <Shield size={12} className="text-white" />
          </div>
          <span className="text-sm font-bold text-white group-hover:text-blue-300 transition-colors">TrustLayer</span>
        </button>
        <span className="text-slate-700 hidden sm:block">|</span>
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider hidden sm:block">Identity Trust Framework</span>

        {/* Desktop nav */}
        <div className="ml-auto hidden sm:flex items-center gap-2">
          {role && <span className="text-[10px] font-mono text-slate-600 bg-slate-800 px-2 py-1 rounded">{role}</span>}
          {isAdmin && (
            <button
              onClick={() => navTo('admin')}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors ${
                page === 'admin' ? 'text-purple-400 bg-purple-950/40' : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <SlidersHorizontal size={12} />Admin
            </button>
          )}
          <button
            onClick={() => navTo('audit')}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-colors ${
              page === 'audit' ? 'text-blue-400 bg-blue-950/40' : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            <FileText size={12} />Audit Log
          </button>
          {result && (
            <button
              onClick={() => navTo('result')}
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

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileMenuOpen(v => !v)}
          className="ml-auto sm:hidden text-slate-400 hover:text-white p-1"
        >
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </nav>

      {/* Mobile dropdown menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
            className="sm:hidden border-b border-slate-800 bg-[#0f1117] px-4 py-3 space-y-1 z-30 relative"
          >
            {role && (
              <div className="px-3 py-2 text-[10px] font-mono text-slate-500 bg-slate-800/50 rounded-lg">
                Signed in as <span className="text-slate-300">{role}</span>
              </div>
            )}
            {isAdmin && (
              <button onClick={() => navTo('admin')}
                className="w-full flex items-center gap-2 text-sm px-3 py-2.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors text-left">
                <SlidersHorizontal size={14} />Admin Console
              </button>
            )}
            <button onClick={() => navTo('audit')}
              className="w-full flex items-center gap-2 text-sm px-3 py-2.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors text-left">
              <FileText size={14} />Audit Log
            </button>
            {result && (
              <button onClick={() => navTo('result')}
                className="w-full flex items-center gap-2 text-sm px-3 py-2.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors text-left">
                <Activity size={14} />Last Assessment
              </button>
            )}
            <button onClick={handleLogout}
              className="w-full flex items-center gap-2 text-sm px-3 py-2.5 rounded-lg text-red-500 hover:text-red-400 hover:bg-red-950/20 transition-colors text-left">
              <LogOut size={14} />Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>

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
            <MetricsDashboard
              role={role}
              onStart={() => setPage('form')}
              onViewAudit={() => setPage('audit')}
            />
          )}
          {page === 'form' && !isAuditor && (
            <OnboardingForm
              onResult={handleResult}
              onProgress={handleProgress}
              onBack={() => setPage('dashboard')}
            />
          )}
          {page === 'admin' && isAdmin && (
            <AdminPanel onBack={() => setPage('dashboard')} />
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
