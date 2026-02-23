import { Quaternion } from 'three';
import type { Colony } from '../types/Types';

export const sampleColonies: Colony[] = [
  {
    id: '1',
    name: "New Terra",
    residents: 15000,
    color: "#4A90E2",
    planet: {
      position: { x: 0, y: 0, z: 0 },
      scale: 1,
      rot: { x: 0, y: 0, z: 0 },
      planetModelName: "Planet_A",
      planetMainBase: { x: 3, y: 6},
      planetNaturalResources: {
        water: 1.3,
        steel: 0.8,
        oil: 1.1,
        temperature: 15
      },
    },
    colonyLevel: 'Metropolis',
    colonyFleet: [{
      id: '400',
      type: 'Attacker',
      position: {
        x: 10,
        y: 0,
        z: 0
      },
      velocity: {
        x: 0,
        y: 0,
        z: 0
      },
      rotation: new Quaternion,
      state: 'Idle',
      tactic: 'Offensive',
      count: 3,
      isAttacking: false,
      target: {position: {x: 0, y: 0, z: 0}},
      order: {
        type: 'Move',
        targetPos: { x: 50, y: 0, z: 0}
      }
    },
    {
      id: '401',
      type: 'Fighter',
      label: 'Fighter Sq',
      position: { x: 14, y: 5, z: 0 },
      velocity: { x: 0, y: 0, z: 0 },
      rotation: new Quaternion(),
      state: 'Moving',
      tactic: 'Offensive',
      count: 5,
      order: {
        type: 'Move',
        targetPos: { x: 60, y: 10, z: 0}
      }
    },
    {
      id: '402',
      type: 'Bomber',
      label: 'Bomber Wing',
      position: { x: 10, y: -5, z: 0 },
      velocity: { x: 0, y: 0, z: 0 },
      rotation: new Quaternion(),
      state: 'Moving',
      tactic: 'Offensive',
      count: 2,
      order: {
        type: 'Move',
        targetPos: { x: 50, y: -10, z: 0}
      }
    },
    {
      id: '403',
      type: 'Scout',
      label: 'Scout 1',
      position: { x: 8, y: 0, z: 5 },
      velocity: { x: 0, y: 0, z: 0 },
      rotation: new Quaternion(),
      state: 'Moving',
      tactic: 'Offensive',
      count: 1,
      order: {
        type: 'Move',
        targetPos: { x: 55, y: 0, z: 10}
      }
    }]
  },
  {
    id: '2',
    name: "Aurora Station",
    residents: 8500,
    color: "#7ED321",
    planet: {
      position: { x: 72, y: 5, z: -10 },
      scale: 0.8,
      rot: { x: 0.2, y: 1.5, z: 0 },
      planetModelName: "Planet_A",
      planetMainBase: { x: 25, y: 6},
      planetNaturalResources: {
        water: 1.8,
        steel: 0.2,
        oil: 1.3,
        temperature: 5
      }
    },
    colonyLevel: 'Colony'
  },
  {
    id: '3',
    name: "Crimson Outpost",
    residents: 12300,
    color: "#D0021B",
    planet: {
      position: { x: -80, y: -15, z: 85 },
      scale: 1.2,
      rot: { x: -0.3, y: -0.8, z: 0.1 },
      planetModelName: "Planet_A",
      planetMainBase: { x: -42, y: 21},
      planetNaturalResources: {
        water: 0.5,
        steel: 0.3,
        oil: 0.8,
        temperature: 28
      }
    },
    colonyLevel: 'Colony'
  },
  {
    id: '4',
    name: "Azure Haven",
    residents: 20000,
    color: "#50E3C2",
    planet: {
      position: { x: 10, y: 52, z: -55 },
      scale: 0.9,
      rot: { x: 0.5, y: 2.1, z: -0.2 },
      planetModelName: "Planet_A",
      planetMainBase: { x: 55, y: 42},
      planetNaturalResources: {
        water: 1.8,
        steel: 1.5,
        oil: 1.3,
        temperature: -15
      }
    },
    colonyLevel: 'Colony'
  }
];