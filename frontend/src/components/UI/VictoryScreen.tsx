import { useEffect, useRef, useState } from 'react'
import type { GameOverPayload, ActionEvent } from '../../types/Types'

type Props = {
  gameOver: GameOverPayload
  onRestart: () => void
}

export default function VictoryScreen({ gameOver, onRestart }: Props) {
  const [secondsLeft, setSecondsLeft] = useState(() => {
    const diff = gameOver.restartAt - Date.now() / 1000
    return Math.max(0, Math.ceil(diff))
  })
  const scrollRef = useRef<HTMLDivElement>(null)

  // Countdown timer
  useEffect(() => {
    const id = setInterval(() => {
      const diff = gameOver.restartAt - Date.now() / 1000
      const remaining = Math.max(0, Math.ceil(diff))
      setSecondsLeft(remaining)

      if (remaining <= 0) {
        clearInterval(id)
        onRestart()
      }
    }, 250)

    return () => clearInterval(id)
  }, [gameOver.restartAt, onRestart])

  // Auto-scroll the log to bottom on mount
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [])

  const getEventIcon = (type: ActionEvent['type']) => {
    switch (type) {
      case 'build': return '🏗️'
      case 'upgrade': return '⬆️'
      case 'level-up': return '⭐'
      case 'attack': return '⚔️'
      case 'destroy': return '💥'
      case 'victory': return ''
      default: return '📋'
    }
  }

  const getEventColor = (type: ActionEvent['type']) => {
    switch (type) {
      case 'build': return '#60a5fa'
      case 'upgrade': return '#4ade80'
      case 'level-up': return '#facc15'
      case 'attack': return '#f87171'
      case 'destroy': return '#fb923c'
      case 'victory': return '#c084fc'
      default: return '#9ca3af'
    }
  }

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp * 1000)
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  const minutes = Math.floor(secondsLeft / 60)
  const seconds = secondsLeft % 60
  const timerDisplay = `${minutes}:${seconds.toString().padStart(2, '0')}`

  return (
    <div className="victory-overlay">
      <div className="victory-panel">
        {/* Winner announcement */}
        <div className="victory-header">
          <span className="victory-trophy"></span>
          <h1 className="victory-title">Victory</h1>
          <p className="victory-subtitle">
            <span className="victory-winner-name" style={{ color: gameOver.winner.color }}>
              {gameOver.winner.name}
            </span>{' '}
            has conquered the galaxy!
          </p>
        </div>

        {/* Game Log */}
        <div className="victory-log-wrapper">
          <h2 className="victory-log-title">Game Log</h2>
          <div className="victory-log" ref={scrollRef}>
            {gameOver.actionHistory.length === 0 ? (
              <div className="victory-log-empty">No events recorded.</div>
            ) : (
              gameOver.actionHistory.map((event, idx) => (
                <div key={event.id ?? idx} className="victory-log-entry">
                  <span className="victory-log-icon">{getEventIcon(event.type)}</span>
                  <span className="victory-log-time">{formatTime(event.timestamp)}</span>
                  <span className="victory-log-colony" style={{ color: getEventColor(event.type) }}>
                    {event.colonyName}
                  </span>
                  <span className="victory-log-msg">{event.message}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Restart timer */}
        <div className="victory-timer-section">
          <p className="victory-timer-label">New game starting in</p>
          <div className="victory-timer">{timerDisplay}</div>
        </div>
      </div>
    </div>
  )
}
