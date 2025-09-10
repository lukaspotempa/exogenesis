import { useGLTF } from '@react-three/drei';
import type { Fleet } from '../../../types/Types';
import { useRef, useEffect, type RefObject } from 'react';
import * as THREE from 'three';
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

  // keep fleetRef in sync when parent replaces fleetProp

  // Simple physics integration per frame: apply velocity to position and notify parent when position changes.
  useFrame((_, delta) => {
    const f = fleetRef.current;
    if (!f) return;

    // Handle Move order: compute desired velocity toward the order's targetPos (world space)
    if (f.order?.type === 'Move' && f.order.targetPos && groupRef.current) {
      // convert world target pos to the local space of the fleet's parent group
      const targetWorld = new THREE.Vector3(
        f.order.targetPos.x,
        f.order.targetPos.y,
        f.order.targetPos.z ?? 0
      );

      const parent = groupRef.current.parent as THREE.Object3D | null;
      const localTarget = parent ? parent.worldToLocal(targetWorld.clone()) : targetWorld;

      const currentPos = new THREE.Vector3(f.position.x, f.position.y, f.position.z);
      const toTarget = localTarget.clone().sub(currentPos);
      const dist = toTarget.length();


      const ARRIVE_THRESHOLD = 0.2;
      const MAX_SPEED = 1.5;
      const ROTATION_DURATION = 0.5; 

      if (dist > ARRIVE_THRESHOLD) {
        const desired = toTarget.normalize().multiplyScalar(MAX_SPEED);
        f.velocity = { x: desired.x, y: desired.y, z: desired.z };
        f.state = 'Moving';
        // compute desired orientation so fleet faces movement direction
        if (groupRef.current) {
          const originWorld = new THREE.Vector3();
          groupRef.current.getWorldPosition(originWorld);
          const targetWorldPos = targetWorld; // defined above

          // world quaternion that looks from origin toward the target
          const lookMat = new THREE.Matrix4().lookAt(targetWorldPos, originWorld, new THREE.Vector3(0, 1, 0));
          const worldQuat = new THREE.Quaternion().setFromRotationMatrix(lookMat);

          // convert world quaternion to group's local quaternion space
          const parent = groupRef.current.parent as THREE.Object3D | null;
          let localTargetQuat = worldQuat.clone();
          if (parent) {
            const parentWorldQuat = new THREE.Quaternion();
            parent.getWorldQuaternion(parentWorldQuat);
            localTargetQuat = parentWorldQuat.clone().invert().multiply(worldQuat);
          }

          // slerp current local quaternion toward the target over ROTATION_DURATION seconds
          const t = Math.min(1, delta / ROTATION_DURATION);
          groupRef.current.quaternion.slerp(localTargetQuat, t);

          // persist rotation to fleet ref and notify parent
          f.rotation = groupRef.current.quaternion.clone();
          onUpdate?.({ ...f });
        }
      } else {
        f.velocity = { x: 0, y: 0, z: 0 };
        const clearedFleet: Fleet = { ...f, order: undefined, state: 'Idle' };
        fleetRef.current = clearedFleet as unknown as Fleet;
        onUpdate?.({ ...clearedFleet });
      }
    }

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

    // fleet movement integration remains here; projectiles are handled by individual ships
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
            <SpaceshipFlanker
              colonyColor={colonyColor ?? '#FFFFFF'}
              isAttacking={!!fleetProp.isAttacking}
              target={fleetProp.target}
            />
          </group>
        );
      })}
    </group>
  );
}

useGLTF.preload('/models/earth/Jupiter-transformed.glb');