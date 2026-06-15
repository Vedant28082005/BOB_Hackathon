import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { User, FileText, Camera, ChevronRight, Upload, ArrowLeft, Shield, RefreshCw } from 'lucide-react'
import { useBiometrics } from '../hooks/useBiometrics'
import {
  fileToBase64, getDeviceFingerprint, getDeviceSignals,
  submitAssessment, waitForResult,
} from '../api/client'
import type { AssessmentResult } from '../types'

interface Props {
  onResult: (r: AssessmentResult) => void
  onProgress: (stage: string, pct: number) => void
  onBack: () => void
}

const STEPS = ['Personal Details', 'Identity Document', 'Selfie Capture']
const DOC_TYPES = ['AADHAAR', 'PAN', 'PASSPORT', 'DRIVING_LICENSE']

export default function OnboardingForm({ onResult, onProgress, onBack }: Props) {
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const [form, setForm] = useState({
    full_name: '', email: '', phone: '', dob: '', address: '', pan_number: '',
    doc_type: 'AADHAAR', doc_name_on_doc: '',
  })
  const [docFile, setDocFile] = useState<File | null>(null)
  const docInputRef = useRef<HTMLInputElement>(null)

  // Webcam selfie state
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [camActive, setCamActive] = useState(false)
  const [camError, setCamError] = useState('')
  const [capturedSelfie, setCapturedSelfie] = useState<string>('') // base64 jpeg

  const startCamera = useCallback(async () => {
    setCamError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: 'user' }, audio: false })
      streamRef.current = stream
      setCamActive(true) // render <video> first, then useEffect attaches the stream
    } catch {
      setCamError('Camera access denied. Please allow camera permission and try again.')
    }
  }, [])

  // Attach stream after <video> mounts (camActive=true triggers the render)
  useEffect(() => {
    if (camActive && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
      videoRef.current.play().catch(() => {})
    }
  }, [camActive])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    setCamActive(false)
  }, [])

  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return
    const v = videoRef.current
    // Wait for a real frame — videoWidth=0 means stream not ready yet
    if (!v.videoWidth || !v.videoHeight) {
      setTimeout(capturePhoto, 200)
      return
    }
    const c = canvasRef.current
    c.width = v.videoWidth
    c.height = v.videoHeight
    const ctx = c.getContext('2d')!
    // Mirror the canvas to match the mirrored video display
    ctx.translate(c.width, 0)
    ctx.scale(-1, 1)
    ctx.drawImage(v, 0, 0, c.width, c.height)
    const b64 = c.toDataURL('image/jpeg', 0.92).split(',')[1]
    setCapturedSelfie(b64)
    stopCamera()
  }, [stopCamera])

  // Stop camera when leaving step 2
  useEffect(() => {
    if (step !== 2) stopCamera()
  }, [step, stopCamera])

  const { onKeyDown, onPaste, onBlur, collect } = useBiometrics()

  const field = (key: keyof typeof form) => ({
    value: form[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm(f => ({ ...f, [key]: e.target.value })),
    onKeyDown, onPaste, onBlur,
  })

  const canNext = () => {
    if (step === 0) return !!(form.full_name && form.email && form.phone && form.dob && form.pan_number)
    return true
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      const doc_image_b64 = docFile ? await fileToBase64(docFile) : ''
      const selfie_b64 = capturedSelfie
      const fingerprint = await getDeviceFingerprint()
      const deviceSignals = getDeviceSignals(fingerprint)
      const behavioural = collect()

      const { job_id } = await submitAssessment({
        ...form,
        doc_image_b64,
        selfie_b64,
        device: deviceSignals,
        behavioural,
      })

      const result = await waitForResult(job_id, onProgress)
      onResult(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Assessment failed. Is the backend running?')
      setSubmitting(false)
    }
  }

  const inputCls = 'w-full bg-[#0f1117] border border-slate-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors'
  const labelCls = 'text-xs font-medium text-slate-400 mb-1 block'

  return (
    <div className="min-h-screen bg-[#0f1117] flex items-start justify-center px-4 py-6 sm:py-10">
      <div className="w-full max-w-2xl">
        <div className="flex items-center gap-3 mb-5 sm:mb-6">
          <button onClick={onBack} className="text-slate-400 hover:text-white transition-colors flex-shrink-0">
            <ArrowLeft size={18} />
          </button>
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center flex-shrink-0">
              <Shield size={12} className="text-white" />
            </div>
            <span className="text-sm font-semibold text-white flex-shrink-0">TrustLayer</span>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-slate-400 truncate">New Assessment</span>
          </div>
        </div>

        {/* Step indicator — compact on mobile */}
        <div className="flex items-center mb-6 sm:mb-8">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center flex-1 last:flex-none">
              <div className={`flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 rounded-lg transition-all ${
                i === step ? 'bg-blue-600/20 border border-blue-600/50' :
                i < step ? '' : ''
              }`}>
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0 ${
                  i < step ? 'bg-green-500 text-white' :
                  i === step ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-500'
                }`}>{i < step ? '✓' : i + 1}</div>
                <span className={`text-xs font-medium hidden sm:block ${i === step ? 'text-blue-300' : i < step ? 'text-green-400' : 'text-slate-600'}`}>{s}</span>
                <span className={`text-[10px] font-medium sm:hidden ${i === step ? 'text-blue-300' : i < step ? 'text-green-400' : 'text-slate-600'}`}>
                  {s.split(' ')[0]}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-px mx-1 ${i < step ? 'bg-green-700' : 'bg-slate-700'}`} />
              )}
            </div>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {step === 0 && (
            <motion.div key="step0" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <div className="rounded-xl border border-slate-700/60 bg-[#151821] p-6 space-y-4">
                <div className="flex items-center gap-2 mb-2">
                  <User size={15} className="text-blue-400" />
                  <h2 className="text-sm font-semibold text-white">Personal Details</h2>
                  <span className="ml-auto text-[10px] font-mono text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
                    Biometric capture active
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                  <div className="sm:col-span-2">
                    <label className={labelCls}>Full Name *</label>
                    <input className={inputCls} placeholder="As per identity document" {...field('full_name')} />
                  </div>
                  <div>
                    <label className={labelCls}>Email Address *</label>
                    <input type="email" className={inputCls} placeholder="applicant@example.com" {...field('email')} />
                  </div>
                  <div>
                    <label className={labelCls}>Mobile Number *</label>
                    <input className={inputCls} placeholder="10-digit mobile" {...field('phone')} />
                  </div>
                  <div>
                    <label className={labelCls}>Date of Birth *</label>
                    <input type="date" className={inputCls} {...field('dob')} />
                  </div>
                  <div>
                    <label className={labelCls}>PAN Number *</label>
                    <input className={inputCls} placeholder="ABCDE1234F" {...field('pan_number')} />
                  </div>
                  <div className="sm:col-span-2">
                    <label className={labelCls}>Address</label>
                    <input className={inputCls} placeholder="Current residential address" {...field('address')} />
                  </div>
                </div>
                <div className="mt-2 px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700/40 text-[11px] text-slate-400 font-mono flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                  Keystroke biometrics capture running — timing data collected for bot detection
                </div>
              </div>
            </motion.div>
          )}

          {step === 1 && (
            <motion.div key="step1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <div className="rounded-xl border border-slate-700/60 bg-[#151821] p-6 space-y-4">
                <div className="flex items-center gap-2 mb-2">
                  <FileText size={15} className="text-blue-400" />
                  <h2 className="text-sm font-semibold text-white">Identity Document</h2>
                </div>
                <div>
                  <label className={labelCls}>Document Type *</label>
                  <select className={inputCls} {...field('doc_type')}>
                    {DOC_TYPES.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
                  </select>
                </div>
                <div>
                  <label className={labelCls}>Name on Document</label>
                  <input className={inputCls} placeholder="Exactly as printed on document" {...field('doc_name_on_doc')} />
                </div>
                <div>
                  <label className={labelCls}>Upload Document</label>
                  <div
                    onClick={() => docInputRef.current?.click()}
                    className={`cursor-pointer border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                      docFile ? 'border-green-600/60 bg-green-950/20' : 'border-slate-700 hover:border-blue-600/60 bg-slate-800/20'
                    }`}
                  >
                    <input ref={docInputRef} type="file" className="hidden" accept="image/*,.pdf"
                      onChange={e => setDocFile(e.target.files?.[0] ?? null)} />
                    {docFile ? (
                      <>
                        <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-2">
                          <FileText size={20} className="text-green-400" />
                        </div>
                        <p className="text-sm text-green-400 font-medium">{docFile.name}</p>
                        <p className="text-xs text-slate-500 mt-1">Sent to ML service for OCR + forensics · Purged from MinIO after 24h</p>
                      </>
                    ) : (
                      <>
                        <Upload size={24} className="text-slate-500 mx-auto mb-2" />
                        <p className="text-sm text-slate-400">Click to upload document image</p>
                        <p className="text-xs text-slate-600 mt-1">PaddleOCR · ELA · EXIF · Copy-move forensics · PAN/Aadhaar checksum</p>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <div className="rounded-xl border border-slate-700/60 bg-[#151821] p-6 space-y-4">
                <div className="flex items-center gap-2 mb-2">
                  <Camera size={15} className="text-blue-400" />
                  <h2 className="text-sm font-semibold text-white">Liveness & Selfie</h2>
                  <span className="ml-auto text-[10px] font-mono text-slate-500 bg-slate-800 px-2 py-0.5 rounded">Live webcam required</span>
                </div>

                {/* Captured preview */}
                {capturedSelfie ? (
                  <div className="relative rounded-xl overflow-hidden border border-green-600/50 bg-black">
                    <img src={`data:image/jpeg;base64,${capturedSelfie}`} alt="Captured selfie"
                      className="w-full max-h-72 object-contain" />
                    <div className="absolute top-2 right-2">
                      <button onClick={() => { setCapturedSelfie(''); startCamera() }}
                        className="flex items-center gap-1.5 text-xs bg-slate-900/80 border border-slate-600 text-slate-300 px-3 py-1.5 rounded-lg hover:border-blue-500 transition-colors">
                        <RefreshCw size={12} /> Retake
                      </button>
                    </div>
                    <div className="absolute bottom-2 left-2 bg-green-900/80 border border-green-600/60 rounded-lg px-3 py-1 text-xs text-green-300 font-mono">
                      ✓ Photo captured — ready for liveness analysis
                    </div>
                  </div>
                ) : camActive ? (
                  /* Live camera feed */
                  <div className="relative rounded-xl overflow-hidden border border-blue-600/50 bg-black" style={{ minHeight: '280px' }}>
                    <video ref={videoRef} autoPlay muted playsInline
                      className="w-full block"
                      style={{ transform: 'scaleX(-1)', minHeight: '280px', objectFit: 'cover' }} />
                    <div className="absolute inset-0 pointer-events-none">
                      {/* Face oval guide */}
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-44 h-56 rounded-full border-2 border-blue-400/60 border-dashed" />
                      </div>
                    </div>
                    <div className="absolute bottom-3 inset-x-0 flex justify-center z-10">
                      <button onClick={capturePhoto}
                        className="w-14 h-14 rounded-full bg-white border-4 border-blue-500 hover:scale-105 transition-transform shadow-xl flex items-center justify-center cursor-pointer">
                        <Camera size={22} className="text-blue-600" />
                      </button>
                    </div>
                    <div className="absolute top-2 left-2 bg-red-900/70 border border-red-600/50 rounded px-2 py-0.5 text-[10px] text-red-300 font-mono flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" /> LIVE
                    </div>
                  </div>
                ) : (
                  /* Start camera prompt */
                  <div className="border-2 border-dashed border-slate-700 hover:border-blue-600/60 rounded-xl p-10 text-center transition-all">
                    <Camera size={36} className="text-slate-500 mx-auto mb-3" />
                    <p className="text-sm text-slate-300 font-medium mb-1">Live Face Capture</p>
                    <p className="text-xs text-slate-500 mb-4">Position your face in the oval and click the shutter button</p>
                    {camError && <p className="text-xs text-red-400 mb-3">{camError}</p>}
                    <button onClick={startCamera}
                      className="mx-auto flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-all">
                      <Camera size={15} /> Open Camera
                    </button>
                  </div>
                )}

                <canvas ref={canvasRef} className="hidden" />

                <div className="grid grid-cols-3 gap-2 text-[11px] text-slate-500">
                  {['ArcFace Match', 'MiniFASNet Liveness', 'EfficientNet-B4 Deepfake'].map(t => (
                    <div key={t} className={`rounded-lg px-2 py-1.5 text-center border transition-colors ${capturedSelfie ? 'border-green-700/40 bg-green-950/20 text-green-500' : 'border-slate-700/40 bg-slate-800/50'}`}>{t}</div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <div className="mt-4 px-4 py-3 rounded-lg bg-red-950/40 border border-red-700/60 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="flex items-center justify-between mt-6">
          <button
            onClick={() => step > 0 ? setStep(s => s - 1) : onBack()}
            className="px-4 py-2.5 rounded-lg border border-slate-700 text-sm text-slate-400 hover:text-white hover:border-slate-500 transition-all"
          >
            {step > 0 ? '← Back' : '← Dashboard'}
          </button>
          {step < STEPS.length - 1 ? (
            <button
              disabled={!canNext()}
              onClick={() => setStep(s => s + 1)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold transition-all"
            >
              Next <ChevronRight size={15} />
            </button>
          ) : (
            <button
              disabled={submitting}
              onClick={handleSubmit}
              className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold transition-all"
            >
              {submitting ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Analysing…
                </>
              ) : (
                <>Run Assessment →</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
