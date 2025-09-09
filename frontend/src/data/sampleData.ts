import { Colony } from '../types/Types';

export const sampleColonies: Colony[] = [
  {
    name: "New Terra",
    residents: 15000,
    color: "#4A90E2",
    planet: {
      position: { x: 0, y: 0, z: 0 },
      scale: 1,
      rot: { x: 0, y: 0, z: 0 },
      planetModelName: "Planet_A"
    }
  },
  {
    name: "Aurora Station",
    residents: 8500,
    color: "#7ED321",
    planet: {
      position: { x: 25, y: 5, z: -10 },
      scale: 0.8,
      rot: { x: 0.2, y: 1.5, z: 0 },
      planetModelName: "Planet_A"
    }
  },
  {
    name: "Crimson Outpost",
    residents: 12300,
    color: "#D0021B",
    planet: {
      position: { x: -20, y: -8, z: 15 },
      scale: 1.2,
      rot: { x: -0.3, y: -0.8, z: 0.1 },
      planetModelName: "Planet_A"
    }
  },
  {
    name: "Azure Haven",
    residents: 20000,
    color: "#50E3C2",
    planet: {
      position: { x: 10, y: 15, z: -25 },
      scale: 0.9,
      rot: { x: 0.5, y: 2.1, z: -0.2 },
      planetModelName: "Planet_A"
    }
  }
];