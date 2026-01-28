import type { Quaternion } from "three";

export interface Colony {
    id: string;
    name: string;
    residents: number;
    color: string;
    planet: Planet;
    colonyLevel: ColonyLevel;
    colonyFleet?: Fleet[];
}

export interface Planet {
    position: { x: number, y: number, z: number }
    scale: number;
    rot: { x: number, y: number, z: number };
    planetModelName: string;
    planetMainBase: { x: number, y: number }; // Main base location on a planet
    planetNaturalResources: NaturalResources;
    planetResourceStation?: ResourceStation[];
    oilPumps?: OilPump[];
}

export interface NaturalResources {
    oil: number;
    steel: number;
    water: number;
    temperature: number;
    oilStorage?: number;
    steelStorage?: number;
    waterStorage?: number;
}

export interface ResourceStation { // Resource Outposts like drilling stations, only available on planets
    position: { x: number, y: number }
    resourceType: keyof NaturalResources;
}

export interface OilPump {
    id: string;
    position: { x: number, y: number };
    production: number;
}

export type ColonyLevel = 'Colony' | 'Settlement' | 'Township' | 'Metropolis' | 'Starport Hub';

export interface Fleet {
    id: string;
    type: 'Attacker' | 'Flanker' | 'Fighter' | 'Bomber';
    label?: string;
    count?: number;
    position: { x: number, y: number, z: number };
    velocity: { x: number, y: number, z: number };
    rotation?: Quaternion;
    state: FleetState;
    tactic: FleetTactic;
    order?: FleetOrder;
    leaderId?: string;           // optional leader ship id for formations
    hpPool?: number;   
    target?: { id?: string; position?: { x: number; y: number; z?: number } };
    isAttacking?: boolean;
}

export interface FleetOrder {
    type: 'Move' | 'Attack' | 'Patrol' | 'Hold' | 'Retreat' | 'Dock';
    targetId?: string; // id of planet/colony/fleet
    targetPos?: { x: number, y: number, z?: number };
    timestamp?: number;
}

export interface SpaceShip {
    label: string;
    model: string;
}

export type FleetState = 'Idle' | 'Moving' | 'Attacking' | 'Retreating' | 'Patrolling' | 'Docking';

export type FleetTactic = 'Offensive' | 'Defensive' | 'Skirmish' | 'Kite' | 'Hold';

export interface ActionEvent {
    id: string;
    timestamp: number;
    colonyId: string;
    colonyName: string;
    message: string;
    type: 'build' | 'upgrade' | 'attack' | 'destroy' | 'level-up' | 'general';
}