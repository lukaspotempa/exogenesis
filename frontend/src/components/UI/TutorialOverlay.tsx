import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'exogenesis_tutorial_seen'

interface TutorialStep {
  id: string
  title: string
  description: string
  hint?: string
  detect: (onComplete: () => void) => () => void // returns cleanup fn
}

const STEPS: TutorialStep[] = [
  {
    id: 'zoom',
    title: 'Zoom',
    description: 'Use the scroll wheel or middle mouse button to zoom in and out.',
    hint: 'Try scrolling now',
    detect: (onComplete) => {
      const handler = () => onComplete()
      window.addEventListener('wheel', handler, { passive: true })
      return () => window.removeEventListener('wheel', handler)
    },
  },
  {
    id: 'pan',
    title: 'Pan Camera',
    description: 'Hold Shift and left-click drag to move the camera.',
    hint: 'Try holding Shift + Left Mouse and dragging',
    detect: (onComplete) => {
      let triggered = false
      const handler = (e: MouseEvent) => {
        if (!triggered && e.shiftKey && e.buttons === 1) {
          triggered = true
          onComplete()
        }
      }
      window.addEventListener('mousemove', handler)
      return () => window.removeEventListener('mousemove', handler)
    },
  },
  {
    id: 'rotate',
    title: 'Rotate Camera',
    description: 'Left-click and drag (without Shift) to rotate the camera.',
    hint: 'Try clicking and dragging on the scene',
    detect: (onComplete) => {
      let triggered = false
      const handler = (e: MouseEvent) => {
        if (!triggered && !e.shiftKey && e.buttons === 1) {
          triggered = true
          onComplete()
        }
      }
      window.addEventListener('mousemove', handler)
      return () => window.removeEventListener('mousemove', handler)
    },
  },
  {
    id: 'select-planet',
    title: 'Select a Planet',
    description: 'Click on a planet in the scene to lock the camera on it.',
    hint: 'Click any planet visible in the scene',
    detect: (onComplete) => {
      const handler = () => onComplete()
      window.addEventListener('planetSelected', handler)
      return () => window.removeEventListener('planetSelected', handler)
    },
  },
]

type Phase = 'prompt' | 'active' | 'done' | 'hidden'

export default function TutorialOverlay() {
  const [phase, setPhase] = useState<Phase>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true' ? 'hidden' : 'prompt'
    } catch {
      return 'prompt'
    }
  })

  const [stepIndex, setStepIndex] = useState(0)
  const [completingStep, setCompletingStep] = useState(false)

  const dismiss = useCallback((saveToStorage: boolean) => {
    if (saveToStorage) {
      try { localStorage.setItem(STORAGE_KEY, 'true') } catch { /* ignore */ }
    }
    setPhase('hidden')
  }, [])

  const advanceStep = useCallback(() => {
    if (completingStep) return
    setCompletingStep(true)
    setTimeout(() => {
      setStepIndex(prev => {
        const next = prev + 1
        if (next >= STEPS.length) {
          setPhase('done')
          try { localStorage.setItem(STORAGE_KEY, 'true') } catch { /* ignore */ }
          setTimeout(() => setPhase('hidden'), 2500)
        }
        return next
      })
      setCompletingStep(false)
    }, 300)
  }, [completingStep])

  // Attach/detach the detector for the current step
  useEffect(() => {
    if (phase !== 'active') return
    const step = STEPS[stepIndex]
    if (!step) return
    const cleanup = step.detect(advanceStep)
    return cleanup
  }, [phase, stepIndex, advanceStep])

  if (phase === 'hidden') return null

  // ── Prompt ─────────────────────────────────────────────────────────────────
  if (phase === 'prompt') {
    return (
      <div className="tutorial-overlay tutorial-prompt">
        <div className="tutorial-prompt-box">
          <h2 className="tutorial-prompt-title">Welcome to Exogenesis</h2>
          <p className="tutorial-prompt-text">
            Would you like a quick tutorial on how to navigate the galaxy?
          </p>
          <div className="tutorial-prompt-actions">
            <button
              className="tutorial-btn tutorial-btn-primary"
              onClick={() => setPhase('active')}
            >
              Yes, let's go!
            </button>
            <button
              className="tutorial-btn tutorial-btn-secondary"
              onClick={() => dismiss(true)}
            >
              No thanks
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Done ────────────────────────────────────────────────────────────────────
  if (phase === 'done') {
    return (
      <div className="tutorial-overlay tutorial-done-banner">
        <div className="tutorial-done-box">
          <span className="tutorial-done-icon">✓</span>
          <span>Tutorial complete! Enjoy the game.</span>
        </div>
      </div>
    )
  }

  // ── Active step ─────────────────────────────────────────────────────────────
  const step = STEPS[stepIndex]
  if (!step) return null

  return (
    <div className="tutorial-overlay tutorial-step-banner">
      <div className="tutorial-step-box">
        <div className="tutorial-step-content">
          <div className="tutorial-step-header">
            <span className="tutorial-step-counter">
              Step {stepIndex + 1} / {STEPS.length}
            </span>
            <span className="tutorial-step-title">{step.title}</span>
          </div>
          <p className="tutorial-step-desc">{step.description}</p>
          {step.hint && (
            <p className="tutorial-step-hint">{step.hint}</p>
          )}
        </div>
        <div className="tutorial-step-actions">
          <button
            className="tutorial-btn tutorial-btn-secondary"
            onClick={advanceStep}
          >
            Skip
          </button>
          <button
            className="tutorial-btn tutorial-btn-danger"
            onClick={() => dismiss(true)}
          >
            End Tutorial
          </button>
        </div>
      </div>
    </div>
  )
}
