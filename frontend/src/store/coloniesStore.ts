import type { Colony } from '../types/Types';

class ColoniesStore {
    private colonies: Colony[] = [];
    private listeners: (() => void)[] = [];
    private activeColony: Colony | undefined;

    setColonies(colonies: Colony[]) {
        this.colonies = colonies;
        this.notifyListeners();
    }

    getColonies(): Colony[] {
        return this.colonies;
    }

    addColony(colony: Colony) {
        this.colonies.push(colony);
        this.notifyListeners();
    }

    removeColony(name: string) {
        this.colonies = this.colonies.filter(colony => colony.name !== name);
        this.notifyListeners();
    }

    updateColonies(changes: Partial<Colony>[]): void {
        let hasUpdates = false;
        
        changes.forEach(change => {
            if (!change.id) return;
            
            const colonyIndex = this.colonies.findIndex(colony => colony.id === change.id);
            if (colonyIndex === -1) return;
            
            // Create updated colony by merging changes
            const existingColony = this.colonies[colonyIndex];
            const updatedColony: Colony = {
                ...existingColony,
                ...change,
                planet: change.planet ? {
                    ...existingColony.planet,
                    ...change.planet,
                    planetNaturalResources: change.planet.planetNaturalResources ? {
                        ...existingColony.planet.planetNaturalResources,
                        ...change.planet.planetNaturalResources
                    } : existingColony.planet.planetNaturalResources,
                    position: change.planet.position ? {
                        ...existingColony.planet.position,
                        ...change.planet.position
                    } : existingColony.planet.position,
                    rot: change.planet.rot ? {
                        ...existingColony.planet.rot,
                        ...change.planet.rot
                    } : existingColony.planet.rot,
                    planetMainBase: change.planet.planetMainBase ? {
                        ...existingColony.planet.planetMainBase,
                        ...change.planet.planetMainBase
                    } : existingColony.planet.planetMainBase,
                } : existingColony.planet,
                colonyFleet: change.colonyFleet !== undefined ? change.colonyFleet : existingColony.colonyFleet
            };
            
            this.colonies[colonyIndex] = updatedColony;
            hasUpdates = true;
            
            if (this.activeColony && this.activeColony.id === change.id) {
                this.activeColony = updatedColony;
            }
        });
        
        if (hasUpdates) {
            this.notifyListeners();
        }
    }

    subscribe(listener: () => void) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    setActiveColony(colony: Colony) {
        this.activeColony = colony;
        this.notifyListeners();
    }

    getActiveColony(): Colony | undefined {
        return this.activeColony;
    }

    removeActiveColony() {
        this.activeColony = undefined;
        this.notifyListeners();
    }

    private notifyListeners() {
        this.listeners.forEach(listener => listener());
    }
}

export const coloniesStore = new ColoniesStore();