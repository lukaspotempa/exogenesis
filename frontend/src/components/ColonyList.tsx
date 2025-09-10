import React from 'react'
import type { Colony } from '../types/Types'

type Props = {
  colonies: Colony[]
  activeColony: string | null
  setActiveColony: (name: string) => void
}

export default function ColonyList({ colonies, activeColony, setActiveColony }: Props) {
  return (
    <div className="ColonyList overflow-hidden rounded-md bg-transparent">
      <table className="min-w-full text-sm text-left">
        <thead>
          <tr className="text-white/70">
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Color</th>
            <th className="px-3 py-2">Colony Name</th>
            <th className="px-3 py-2">Residents</th>
          </tr>
        </thead>
        <tbody>
          {colonies.map((colony, idx) => {
            const isActive = activeColony === colony.name
            return (
              <tr
                key={colony.name}
                onClick={() => setActiveColony(colony.name)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setActiveColony(colony.name); }}
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
                <td className="px-3 py-2 align-middle">{colony.residents.toLocaleString()}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
