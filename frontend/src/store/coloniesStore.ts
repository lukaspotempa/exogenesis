import type { Colony } from '../types/Types';

class ColoniesStore {
    private colonies: Colony[] = [];
    private listeners: (() => void)[] = [];

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

    subscribe(listener: () => void) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    }

    private notifyListeners() {
        this.listeners.forEach(listener => listener());
    }
}

export const coloniesStore = new ColoniesStore();