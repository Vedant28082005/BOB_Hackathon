import { useState } from 'react'
import { Shield, Eye, EyeOff } from 'lucide-react'
import { login } from '../api/client'

interface Props {
  onLogin: (role: string) => void
  sessionExpired?: boolean
}

export default function LoginPage({ onLogin, sessionExpired }: Props) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const { role } = await login(email, password)
      onLogin(role)
    } catch {
      setError('Invalid credentials. Try analyst@trustlayer.in / analyst123')
    } finally {
      setLoading(false)
    }
  }

  const fill = (e: string, p: string) => { setEmail(e); setPassword(p) }

  return (
    <div className="min-h-screen bg-[#0f1117] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-blue-600 flex items-center justify-center mb-3">
            <Shield size={24} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-white">TrustLayer</h1>
          <p className="text-xs text-slate-500 mt-1">Identity Trust Framework</p>
        </div>

        {sessionExpired && (
          <div className="mb-4 px-4 py-3 rounded-xl bg-amber-950/40 border border-amber-700/60 text-xs text-amber-400 text-center">
            Your session expired. Please sign in again.
          </div>
        )}

        {/* Card */}
        <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-700/60 bg-[#151821] p-6 space-y-4">
          <h2 className="text-sm font-semibold text-slate-300 mb-2">Sign in to your account</h2>

          <div>
            <label className="text-xs text-slate-400 mb-1 block">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="analyst@trustlayer.in"
              className="w-full bg-[#0f1117] border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
              required
            />
          </div>

          <div>
            <label className="text-xs text-slate-400 mb-1 block">Password</label>
            <div className="relative">
              <input
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-[#0f1117] border border-slate-700 rounded-lg px-3 py-2.5 pr-10 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
                required
              />
              <button type="button" onClick={() => setShowPw(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300">
                {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          {error && (
            <p className="text-xs text-red-400 bg-red-950/30 border border-red-800/40 rounded-lg px-3 py-2">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold transition-all flex items-center justify-center gap-2"
          >
            {loading ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : null}
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        {/* Demo credentials */}
        <div className="mt-4 rounded-xl border border-blue-800/50 bg-blue-950/20 p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] text-blue-300 uppercase tracking-wider font-mono">Demo accounts</p>
            <span className="text-[10px] text-blue-400/80 font-medium">👆 Tap to auto-fill</span>
          </div>
          <p className="text-[11px] text-slate-400 mb-3 leading-snug">
            Judges: tap any account below to fill the login form automatically, then press <span className="text-slate-200 font-medium">Sign in</span>.
          </p>
          <div className="space-y-1">
            {[
              ['analyst@trustlayer.in', 'analyst123', 'analyst'],
              ['admin@trustlayer.in',   'admin123',   'admin'],
              ['auditor@trustlayer.in', 'auditor123', 'auditor'],
            ].map(([e, p, role]) => (
              <button key={role} onClick={() => fill(e, p)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg border border-slate-800 hover:border-blue-600/60 hover:bg-slate-800 transition-colors text-left group">
                <span className="text-xs text-slate-300 font-mono group-hover:text-blue-300">{e}</span>
                <span className="text-[10px] text-slate-500 bg-slate-800 px-2 py-0.5 rounded font-mono">{role}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
