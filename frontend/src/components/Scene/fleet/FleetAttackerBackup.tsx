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
  const orbitRadiusRef = useRef<number>(0);

  // Ensure ref stays in sync if parent replaces fleetProp reference
  useEffect(() => {
    fleetRef.current = fleetProp;
    
    // When a new authoritative update arrives:
    if (groupRef.current) {
      const serverPos = new THREE.Vector3(fleetProp.position.x, fleetProp.position.y, fleetProp.position.z);
      
      // 1. Update intended orbit radius based on server position
      orbitRadiusRef.current = serverPos.length();
      
      // 2. Drift Check (Snap if too far)
      const dist = groupRef.current.position.distanceTo(serverPos);
      if (dist > 5.0) {
          // Large discrepancy (teleport or packet loss), snap immediately
          groupRef.current.position.copy(serverPos);
      }
      // If distance is small, we mostly IGNORE the server position (except orbit radius)
      // and continue our smooth local simulation. The server update primarily serves
      // to update the velocity vector (which fleetRef picked up above).
    }
  }, [fleetProp]);

  // keep fleetRef in sync when parent replaces fleetProp

  // Simple physics integration per frame: apply velocity to position and notify parent when position changes.
  useFrame((_, delta) => {
    const f = fleetRef.current;
    if (!f) return;
    
    // Initialize orbit radius if not set
    if (orbitRadiusRef.current === 0 && groupRef.current) {
        // Use current visual position length if we have nothing else
        const len = groupRef.current.position.length();
        if (len > 0.1) orbitRadiusRef.current = len;
        else orbitRadiusRef.current = 15.0; // Fallback
    }

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

    // Smoother Movement Logic: "Pure Client Prediction"
    // We rely entirely on the velocity vector to drive the animation.
    // We do NOT reconcile against server position every frame, avoiding jitter.
    // Drifts are corrected only on large discrepancies (handled in useEffect).
    if (groupRef.current) {
       // Step 1: Integrate Velocity (Prediction)
       const vx = f.velocity.x;
       const vy = f.velocity.y;
       const vz = f.velocity.z ?? 0;
       
       groupRef.current.position.x += vx * delta;
       groupRef.current.position.y += vy * delta;
       groupRef.current.position.z += vz * delta;

       // Step 2: Orbit Constraint
       // Force the ship to stay on its designated orbital shell.
       // This prevents "cutting through" the sphere due to linear movement.
       const currentLen = groupRef.current.position.length();
       if (orbitRadiusRef.current > 0 && currentLen > 0.001) {
           // Normalize and scale to orbit radius
           groupRef.current.position.multiplyScalar(orbitRadiusRef.current / currentLen);
       }
       
      // Rotate fleet to face direction of travel based on velocity
      const velocityMagnitude = Math.sqrt(
        f.velocity.x * f.velocity.x + 
        f.velocity.y * f.velocity.y + 
        (f.velocity.z ?? 0) * (f.velocity.z ?? 0)
      );
      
      // Only rotate if fleet is actually moving
      if (velocityMagnitude > 0.01) {
        // Calculate target rotation based on velocity direction
        const targetDirection = new THREE.Vector3(
          f.velocity.x,
          f.velocity.y,
          f.velocity.z ?? 0
        ).normalize();
        
        // Create a quaternion that looks in the direction of movement
        // Using lookAt with up vector pointing up (0, 1, 0)
        const currentPos = new THREE.Vector3(0, 0, 0);
        const lookAtTarget = currentPos.clone().add(targetDirection);
        const upVector = new THREE.Vector3(0, 1, 0);
        
        const lookMatrix = new THREE.Matrix4().lookAt(lookAtTarget, currentPos, upVector);
        const targetQuaternion = new THREE.Quaternion().setFromRotationMatrix(lookMatrix);
        
        // Smoothly interpolate rotation (slerp) for smooth turning
        const rotationSpeed = 0.5; // Optimized for smooth majestic turns
        const t = Math.min(1, delta * rotationSpeed);
        groupRef.current.quaternion.slerp(targetQuaternion, t);
      }
    }

    // fleet movement integration remains here; projectiles are handled by individual ships
  });

  const count = fleetProp.count ?? 1;
  const spacing = 0.6;

  // Arrow/V formation offsets for 3 ships:
  // Ship 0 (leader): front center
  // Ship 1: left-back
  // Ship 2: right-back
  const getFormationOffset = (index: number, totalCount: number): [number, number, number] => {
    if (totalCount === 1) return [0, 0, 0];
    
    if (totalCount === 3) {
      // Arrow formation
      const formations: [number, number, number][] = [
        [0, 0, 0],                              // Leader at front
        [-spacing, 0, spacing * 0.8],           // Left wingman
        [spacing, 0, spacing * 0.8],            // Right wingman
      ];
      return formations[index] || [0, 0, 0];
    }
    
    // Fallback: line formation for other counts
    const offsetX = (index - (totalCount - 1) / 2) * spacing;
    return [offsetX, 0, 0];
  };

  return (
    <group ref={groupRef} dispose={null}>

      {/* Render spaceship models in arrow formation centered on fleet position */}
      {Array.from({ length: count }).map((_, i) => {
        const [offsetX, offsetY, offsetZ] = getFormationOffset(i, count);
        return (
          <group key={`ship-${i}`} position={[offsetX, offsetY, offsetZ]}>
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
