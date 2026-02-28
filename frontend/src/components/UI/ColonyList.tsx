import { useState } from 'react'
import type { Colony, Fleet } from '../../types/Types'

type Props = {
  colonies: Colony[]
  activeColony: Colony
  setActiveColony: (colony: Colony) => void
  onSelectFleet?: (fleet: Fleet, colony: Colony) => void
  activeFleetId?: string
}

const STATE_COLORS: Record<string, string> = {
  Idle:       'text-white/50',
  Moving:     'text-blue-400',
  Attacking:  'text-red-400',
  Patrolling: 'text-green-400',
  Retreating: 'text-yellow-400',
  Docking:    'text-purple-400',
}

export default function ColonyList({ colonies, activeColony, setActiveColony, onSelectFleet, activeFleetId }: Props) {
  const [tab, setTab] = useState<'planets' | 'fleets'>('planets')

  // Derive flat list of all fleets with their owner colony
  const allFleets: { fleet: Fleet; colony: Colony }[] = colonies.flatMap(colony =>
    (colony.colonyFleet ?? []).map(fleet => ({ fleet, colony }))
  )

  return (
    <div className="ColonyList overflow-hidden rounded-md bg-transparent">
      {/* Tab toggle */}
      <div className="flex gap-1 mb-1 px-1">
        <button
          onClick={() => setTab('planets')}
          title="Planets"
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-colors duration-150 ${
            tab === 'planets'
              ? 'bg-blue-600 text-white'
              : 'bg-white/10 text-white/60 hover:bg-white/20 hover:text-white'
          }`}
        >
          {/* Simple planet SVG */}
          <svg viewBox="0 0 18 18" width="14" height="14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="9" cy="9" r="6" fill="currentColor" opacity="0.9"/>
            <ellipse cx="9" cy="9" rx="8.5" ry="2.5" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.6"/>
          </svg>
          Planets
        </button>
        <button
          onClick={() => setTab('fleets')}
          title="Fleets"
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold transition-colors duration-150 ${
            tab === 'fleets'
              ? 'bg-blue-600 text-white'
              : 'bg-white/10 text-white/60 hover:bg-white/20 hover:text-white'
          }`}
        >
          {/* Simple rocket SVG */}
          <svg viewBox="0 0 18 18" width="14" height="14" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
            <path d="M9 1.5c0 0-4.5 3.5-4.5 8a4.5 4.5 0 0 0 9 0C13.5 5 9 1.5 9 1.5z" opacity="0.9"/>
            <path d="M6.5 13.5 5 16h2.5M11.5 13.5 13 16h-2.5" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.7"/>
            <circle cx="9" cy="9" r="1.5" fill="white" opacity="0.85"/>
          </svg>
          Fleets
          {allFleets.length > 0 && (
            <span className="ml-0.5 px-1 rounded-full bg-white/20 text-white text-xs">
              {allFleets.length}
            </span>
          )}
        </button>
      </div>

      {tab === 'planets' && (
        <table className="min-w-full text-sm text-left">
          <thead>
            <tr className="text-white/70">
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Color</th>
              <th className="px-3 py-2">Colony Name</th>
              <th className="px-3 py-2">Level</th>
              <th className="px-3 py-2">Residents</th>
            </tr>
          </thead>
          <tbody>
            {colonies.map((colony, idx) => {
              const isActive = activeColony?.id === colony.id
              return (
                <tr
                  key={colony.id}
                  onClick={() => setActiveColony(colony)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setActiveColony(colony) }}
                  role="button"
                  tabIndex={0}
                  aria-current={isActive ? 'true' : undefined}
                  className={`cursor-pointer transition duration-150 ${isActive ? 'bg-blue-600 text-white' : 'hover:bg-white/5 text-white/80'}`}
                >
                  <td className="px-3 py-2 align-middle">{idx + 1}</td>
                  <td className="px-3 py-2 align-middle">
                    <div
                      className="w-4 h-4 rounded-sm border"
                      style={{ backgroundColor: colony.color }}
                      title={colony.color}
                    />
                  </td>
                  <td className="px-3 py-2 align-middle truncate">{colony.name}</td>
                  <td className="px-3 py-2 align-middle whitespace-nowrap text-white/60 text-xs">{colony.colonyLevel}</td>
                  <td className="px-3 py-2 align-middle">{colony.residents.toLocaleString()}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      {tab === 'fleets' && (
        <table className="min-w-full text-sm text-left">
          <thead>
            <tr className="text-white/70">
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Owner</th>
              <th className="px-3 py-2">State</th>
            </tr>
          </thead>
          <tbody>
            {allFleets.length === 0 && (
              <tr>
                <td colSpan={3} className="px-3 py-4 text-center text-white/40 text-xs">No fleets active</td>
              </tr>
            )}
            {allFleets.map(({ fleet, colony }, idx) => {
              const isActive = activeFleetId === fleet.id
              const stateClass = STATE_COLORS[fleet.state] ?? 'text-white/60'
              return (
                <tr
                  key={fleet.id ?? idx}
                  onClick={() => onSelectFleet?.(fleet, colony)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectFleet?.(fleet, colony) }}
                  role="button"
                  tabIndex={0}
                  aria-current={isActive ? 'true' : undefined}
                  className={`cursor-pointer transition duration-150 ${isActive ? 'bg-blue-600 text-white' : 'hover:bg-white/5 text-white/80'}`}
                >
                  <td className="px-3 py-2 align-middle whitespace-nowrap text-white/80">
                    {fleet.type}
                  </td>
                  <td className="px-3 py-2 align-middle">
                    <div className="flex items-center gap-1.5">
                      <div
                        className="w-3 h-3 rounded-full flex-shrink-0"
                        style={{ backgroundColor: colony.color }}
                      />
                      <span className="truncate max-w-[80px]">{colony.name}</span>
                    </div>
                  </td>
                  <td className={`px-3 py-2 align-middle font-medium ${isActive ? 'text-white' : stateClass}`}>
                    {fleet.state}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
