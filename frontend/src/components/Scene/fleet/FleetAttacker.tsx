import { useGLTF } from '@react-three/drei';
import type { Fleet } from '../../../types/Types';
import { useRef, useEffect, type RefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Group } from 'three';
import { SpaceshipFlanker } from '../../Models/ship/SpaceshipFlanker';


interface FleetProps {
  colonyColor?: string;
  fleetProp: Fleet;
  /**
   * Called when the fleet has an update to bubble back to the parent (e.g. new position/velocity/rotation/state)
   * Receives the updated Fleet object.
   */
  onUpdate?: (fleet: Fleet) => void;
}

/**
 * Contract (inputs/outputs):
 * - input: `fleetProp: Fleet` (current fleet state from parent)
 * - optional input: `onUpdate` callback to inform parent of local changes
 * - output: calls `onUpdate` with an updated Fleet whenever position/velocity/rotation/state are changed locally
 *
 * Behavior: this component is a visual/animation wrapper for a Fleet. It will read `fleetProp`, animate a
 * local ref toward the fleet's target using velocity, and call `onUpdate` when it mutates the fleet object.
 */

export function FleetAttacker({ colonyColor, fleetProp, onUpdate }: FleetProps): React.JSX.Element {
    
    // Keep a mutable ref to the fleet for local animation and diffs
    const fleetRef = useRef<Fleet>(fleetProp) as RefObject<Fleet>;
    const groupRef = useRef<Group | null>(null);

    // Ensure ref stays in sync if parent replaces fleetProp reference
    useEffect(() => {
      fleetRef.current = fleetProp;
    }, [fleetProp]);

    // Simple physics integration per frame: apply velocity to position and notify parent when position changes.
    useFrame((_, delta) => {
      const f = fleetRef.current;
      if (!f) return;

      // integrate velocity
      const newPos = {
        x: f.position.x + f.velocity.x * delta,
        y: f.position.y + f.velocity.y * delta,
        z: f.position.z + (f.velocity.z ?? 0) * delta,
      };

      // cheap equality check
      const moved = newPos.x !== f.position.x || newPos.y !== f.position.y || newPos.z !== f.position.z;
      if (moved) {
        // mutate local ref
        f.position = newPos;
        // bubble the update to parent so top-level app can persist/forward it
        onUpdate?.({ ...f });
      }

      if (groupRef.current) {
        groupRef.current.position.set(f.position.x, f.position.y, f.position.z);
      }
    });

    const count = fleetProp.count ?? 1;
    const spacing = 0.5; // spacing between ships in formation

    return (
      <group ref={groupRef} dispose={null}>
      
        {/* Render spaceship models in a simple formation centered on fleet */}
        {Array.from({ length: count }).map((_, i) => {
          const offsetX = (i - (count - 1) / 2) * spacing;
          const offsetZ = Math.abs(i - (count - 1) / 2) * - spacing; // slight depth spread
          return (
            <group key={`ship-${i}`} position={[offsetX, 0, offsetZ]}>
              <SpaceshipFlanker colonyColor={colonyColor ?? '#FFFFFF'} />
            </group>
          );
        })}
      </group>
    );
}

useGLTF.preload('/models/earth/Jupiter-transformed.glb');