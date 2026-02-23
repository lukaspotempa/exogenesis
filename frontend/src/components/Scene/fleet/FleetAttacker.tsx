import { useGLTF } from '@react-three/drei';
import type { Fleet } from '../../../types/Types';
import { useRef, useEffect, type RefObject } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import type { Group } from 'three';
import { SpaceshipFlanker } from '../../Models/ship/SpaceshipFlanker';
import { SpaceshipFighter } from '../../Models/ship/SpaceshipFighter';
import { SpaceshipBomber } from '../../Models/ship/SpaceshipBomber';
import { SpaceshipScout } from '../../Models/ship/SpaceshipScout';


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
  const lastUpdateTimeRef = useRef<number>(0);

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
      // NOTE: We intentionally do NOT apply fleetProp.rotation here.
      // Rotation is driven purely by the velocity-based computation in useFrame
      // to avoid fighting between server data and local animation.
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

      if (dist > ARRIVE_THRESHOLD) {
        const desired = toTarget.normalize().multiplyScalar(MAX_SPEED);
        f.velocity = { x: desired.x, y: desired.y, z: desired.z };
        f.state = 'Moving';
        // Rotation is handled in the main update loop below (Block B) based on velocity
      } else {

        f.velocity = { x: 0, y: 0, z: 0 };
        const clearedFleet: Fleet = { ...f, order: undefined, state: 'Idle' };
        fleetRef.current = clearedFleet as unknown as Fleet;
        onUpdate?.({ ...clearedFleet });
      }
    }


    if (groupRef.current) {
      
       const vx = f.velocity.x;
       const vy = f.velocity.y;
       const vz = f.velocity.z ?? 0;
       
       groupRef.current.position.x += vx * delta;
       groupRef.current.position.y += vy * delta;
       groupRef.current.position.z += vz * delta;

       const shouldOrbit = f.state === 'Idle' || f.state === 'Patrolling';
       
       const currentLen = groupRef.current.position.length();
       if (shouldOrbit && orbitRadiusRef.current > 0 && currentLen > 0.001) {
           // Normalize and scale to orbit radius
           groupRef.current.position.multiplyScalar(orbitRadiusRef.current / currentLen);
       }

      const rawVelocity = new THREE.Vector3(
        f.velocity.x,
        f.velocity.y,
        f.velocity.z ?? 0
      );
      
      let effectiveVelocity = rawVelocity;
      if (shouldOrbit && groupRef.current.position.lengthSq() > 0.001) {
        const posNorm = groupRef.current.position.clone().normalize();
        const radialComponent = posNorm.multiplyScalar(rawVelocity.dot(posNorm));
        effectiveVelocity = rawVelocity.clone().sub(radialComponent);
      }
      
      const velocityMagnitude = effectiveVelocity.length();
      
      let targetQuaternion: THREE.Quaternion | null = null;
      
      // Use a fixed world-up vector for stable, consistent rotations.
      // A planet-relative up (position.normalize()) shifts every frame as the fleet
      // orbits, causing the target quaternion to oscillate and preventing convergence.
      const up = new THREE.Vector3(0, 1, 0);

      // Case 1: Rotate to face direction of travel (Moving/Patrolling)
      if (velocityMagnitude > 0.01) {
        const targetDirection = effectiveVelocity.clone().normalize();
        
        // Use lookAt to build rotation: aligns model -Z toward the target direction.
        // This matches the model's geometry where -Z = nose (proven by backup).
        const origin = new THREE.Vector3(0, 0, 0);
        const lookAtTarget = origin.clone().add(targetDirection);
        const lookMatrix = new THREE.Matrix4().lookAt(lookAtTarget, origin, up);
        targetQuaternion = new THREE.Quaternion().setFromRotationMatrix(lookMatrix);
      }
      // Case 2: Rotate to face Target (Attacking, stationary)
      else if (f.isAttacking && f.target?.position && groupRef.current) {
        const targetWorld = new THREE.Vector3(
            f.target.position.x, 
            f.target.position.y, 
            f.target.position.z ?? 0
        );
        
        const parent = groupRef.current.parent;
        if (parent) {
            const targetLocal = parent.worldToLocal(targetWorld.clone());
            const currentPos = groupRef.current.position;
            
            const lookMatrix = new THREE.Matrix4().lookAt(targetLocal, currentPos, up);
            targetQuaternion = new THREE.Quaternion().setFromRotationMatrix(lookMatrix);
        }
      }
      
      if (targetQuaternion) {
        // Smoothly interpolate rotation (slerp) for smooth turning
        const rotationSpeed = 2.0;
        const t = Math.min(1, delta * rotationSpeed);
        groupRef.current.quaternion.slerp(targetQuaternion, t);
        
        // Persist rotation to fleet state as a proper THREE.Quaternion (not a plain object)
        f.rotation = groupRef.current.quaternion.clone();
      }
      
      // Persist position changes to fleet state
      f.position = {
        x: groupRef.current.position.x,
        y: groupRef.current.position.y,
        z: groupRef.current.position.z
      };
      
      // Throttle parent updates to 10 p. sec to avoid feedback loops
      const now = performance.now();
      if (onUpdate && (now - lastUpdateTimeRef.current > 100)) {
        lastUpdateTimeRef.current = now;
        onUpdate({ ...f });
      }
    }

    // fleet movement integration remains here; projectiles are handled by individual ships
  });

  const count = fleetProp.count ?? 1;
  const spacing = 0.6;

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

  const getShipComponent = () => {
    switch (fleetProp.type) {
      case 'Fighter': return SpaceshipFighter;
      case 'Bomber': return SpaceshipBomber;
      case 'Scout': return SpaceshipScout;
      case 'Flanker':
      case 'Attacker':
      default: return SpaceshipFlanker;
    }
  };

  const ShipComponent = getShipComponent();

  return (
    <group ref={groupRef} dispose={null}>

      {/* Render spaceship models in arrow formation centered on fleet position */}
      {Array.from({ length: count }).map((_, i) => {
        const [offsetX, offsetY, offsetZ] = getFormationOffset(i, count);
        return (
          <group key={`ship-${i}`} position={[offsetX, offsetY, offsetZ]}>
            <ShipComponent
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