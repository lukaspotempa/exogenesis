import * as THREE from 'three';

/**
 * Global registry mapping colony IDs to the world-space position of their flag.
 *
 * Each Colony component registers its flag's actual world position (computed via
 * raycast against the planet mesh).  Fleet ship components look up the target
 * colony's flag here so projectiles aim at the visual flag, not at the backend's
 * mathematical approximation.
 */
const registry = new Map<string, THREE.Vector3>();

export function registerFlagPosition(colonyId: string, worldPos: THREE.Vector3): void {
  registry.set(colonyId, worldPos.clone());
}

export function getFlagPosition(colonyId: string): THREE.Vector3 | undefined {
  return registry.get(colonyId);
}

export function unregisterFlagPosition(colonyId: string): void {
  registry.delete(colonyId);
}
