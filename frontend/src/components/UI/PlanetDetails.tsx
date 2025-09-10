import type { Colony } from '../../types/Types'
import ResourceBar from './ResourceBar'

type Props = {
    activeColony: Colony
    setActiveColony: (colony: Colony) => void
}

export default function PlanetDetails({ activeColony }: Props) {
    const selected = activeColony
    const resources = selected?.planet?.planetNaturalResources

    return (
        <div className="ColonyList overflow-hidden rounded-md bg-transparent">
            {/* Details card for the selected colony */}
            {selected ? (
                <div className="mb-4 p-3 rounded-md bg-white/5 text-white">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                            <div className="w-6 h-6 rounded-sm border" style={{ backgroundColor: selected.color }} />
                            <h3 className="text-lg font-medium truncate">{selected.name}</h3>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                            <div className="text-xs text-white/70">Residents</div>
                            <div className="font-semibold">{selected.residents.toLocaleString()}</div>
                        </div>

                        <div>
                        </div>

                        <div>
                            <div className="text-xs text-white/70">Oil</div>
                            <ResourceBar value={resources?.oil ?? null} ariaLabel="Oil amount" color="black"/>
                        </div>

                        <div>
                            <div className="text-xs text-white/70">Steel</div>
                            <ResourceBar value={resources?.steel ?? null} ariaLabel="Steel amount" color="#94a3b8" />
                        </div>

                        <div>
                            <div className="text-xs text-white/70">Water</div>
                            <ResourceBar value={resources?.water ?? null} ariaLabel="Water amount" color="#34d5eb" />
                        </div>

                        <div>
                            <div className="text-xs text-white/70">Temperature °C</div>
                            <ResourceBar 
                            value={resources?.temperature ?? null} 
                            min={0}
                            center={15}
                            max={30}
                            ariaLabel="Water amount" 
                            color="yellow"/>
                        </div>
                        
                    </div>
                </div>
            ) : (
                <div className="mb-4 p-3 rounded-md bg-white/3 text-white/70">Select a colony to view planet details</div>
            )}

        </div>
    )
}
