import { useRef, useCallback, useEffect } from 'react'
import type { BehaviouralSignals } from '../types'

/**
 * Captures real keystroke cadence, paste events, focus losses, and
 * form fill duration. Attach returned handlers to form elements.
 */
export function useBiometrics() {
  const keystrokeIntervals = useRef<number[]>([])
  const lastKeystrokeTime = useRef<number | null>(null)
  const formStartTime = useRef<number | null>(null)
  const pasteEvents = useRef(0)
  const focusLosses = useRef(0)

  const onKeyDown = useCallback(() => {
    const now = performance.now()
    if (formStartTime.current === null) {
      formStartTime.current = now
    }
    if (lastKeystrokeTime.current !== null) {
      const interval = now - lastKeystrokeTime.current
      keystrokeIntervals.current.push(interval)
    }
    lastKeystrokeTime.current = now
  }, [])

  const onPaste = useCallback(() => {
    pasteEvents.current += 1
    // Count paste as a "keystroke start" for form timing
    if (formStartTime.current === null) {
      formStartTime.current = performance.now()
    }
  }, [])

  const onBlur = useCallback(() => {
    focusLosses.current += 1
  }, [])

  const reset = useCallback(() => {
    keystrokeIntervals.current = []
    lastKeystrokeTime.current = null
    formStartTime.current = null
    pasteEvents.current = 0
    focusLosses.current = 0
  }, [])

  const collect = useCallback((): BehaviouralSignals => {
    const now = performance.now()
    const duration = formStartTime.current !== null
      ? (now - formStartTime.current) / 1000
      : 0

    return {
      keystroke_intervals_ms: [...keystrokeIntervals.current],
      form_fill_duration_s: Math.round(duration * 10) / 10,
      paste_events: pasteEvents.current,
      focus_losses: focusLosses.current,
    }
  }, [])

  return { onKeyDown, onPaste, onBlur, collect, reset }
}
