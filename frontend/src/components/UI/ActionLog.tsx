import { useEffect, useRef } from 'react'
import type { ActionEvent } from '../../types/Types'

type Props = {
  events: ActionEvent[]
}

export default function ActionLog({ events }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events])

  // Show latest 8 events
  const displayedEvents = events.slice(-8)

  const getEventIcon = (type: ActionEvent['type']) => {
    switch (type) {
      case 'build':
        return '🏗️'
      case 'upgrade':
        return '⬆️'
      case 'level-up':
        return '⭐'
      case 'attack':
        return '⚔️'
      case 'destroy':
        return '💥'
      default:
        return '📋'
    }
  }

  const getEventColor = (type: ActionEvent['type']) => {
    switch (type) {
      case 'build':
        return 'text-blue-400'
      case 'upgrade':
        return 'text-green-400'
      case 'level-up':
        return 'text-yellow-400'
      case 'attack':
        return 'text-red-400'
      case 'destroy':
        return 'text-orange-400'
      default:
        return 'text-gray-400'
    }
  }

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  return (
    <div className="ActionLog">
      <div className="px-3 py-2 bg-black/40 border-b border-white/10">
        <h3 className="text-sm font-semibold text-white/90">Action Log</h3>
      </div>
      <div 
        ref={scrollRef}
        className="overflow-y-auto h-32 px-3 py-2 space-y-1.5"
      >
        {displayedEvents.length === 0 ? (
          <div className="text-xs text-white/40 italic">No events yet...</div>
        ) : (
          displayedEvents.map((event) => (
            <div 
              key={event.id} 
              className="text-xs flex items-start gap-2 animate-fadeIn"
            >
              <span className="text-base leading-none">{getEventIcon(event.type)}</span>
              <div className="flex-1 min-w-0">
                <span className="text-white/50 text-[10px]">{formatTime(event.timestamp)}</span>
                {' '}
                <span className={`font-medium ${getEventColor(event.type)}`}>
                  {event.colonyName}
                </span>
                {' '}
                <span className="text-white/70">{event.message}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
