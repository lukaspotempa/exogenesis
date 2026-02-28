import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import * as THREE from 'three';
import type { Colony as ColonyType, Fleet, ColonyLevel } from '../../types/Types';
import { PlanetA } from './planets/PlanetA';
import { PlanetB } from './planets/PlanetB';
import { ColonyBaseSmall } from './structures/ColonyBaseSmall';
import { ColonyMetropolis } from './structures/ColonyMetropolis';
import { ColonySettlement } from './structures/ColonySettlement';
import { BaseFlag } from './structures/BaseFlag';
import { OilPump } from './structures/OilPump';
import { SteelFactory } from './structures/SteelFactory';
import { BaseDefenseSystem } from './structures/BaseDefenseSystem';
import { StarportHub } from './structures/StarportHub';
import { FleetExplosion } from './effects/FleetExplosion';
import { registerFlagPosition, getFlagPosition, unregisterFlagPosition } from '../../store/flagPositionRegistry';

// Map colony levels to their corresponding base structure components
const COLONY_BASE_STRUCTURES: Record<ColonyLevel, React.ComponentType<{ colonyColor?: string }>> = {
  'Colony': ColonyBaseSmall,
  'Settlement': ColonySettlement,
  'Township': ColonyMetropolis,
  'Metropolis': ColonyMetropolis,
  'Starport Hub': StarportHub,
};

const HEIGHT_OFFSET: Record<string, number> = {
  'Colony': -0.03,
  'Settlement': -0.05,
  'Township': -0.15,
  'Metropolis': -0.15,
  'Starport Hub': 0.35
};

// Get the appropriate base structure component for a given colony level
const getBaseStructure = (colonyLevel: ColonyLevel): React.ComponentType<{ colonyColor?: string }> => {
  return COLONY_BASE_STRUCTURES[colonyLevel] || ColonyBaseSmall; // Fallback to ColonyBaseSmall if level not found
};
import { FleetAttacker } from '../Scene/fleet/FleetAttacker';

interface ColonyProps {
  colony: ColonyType;
}

interface StructureConfig {
  component: React.ComponentType<{ colonyColor?: string }>;
  position: THREE.Vector3; // Local position relative to basePosition
  rotation?: THREE.Euler; // Local rotation relative to baseOrientation
  scale?: number;
}

interface PlacedStructure {
  component: React.ComponentType<{ colonyColor?: string }>;
  position: THREE.Vector3;
  quaternion: THREE.Quaternion;
}

interface FleetComponentProps {
  colonyColor?: string;
  fleetProp: Fleet;
  onUpdate?: (fleet: Fleet) => void;
}

interface PlacedFleet {
  component: React.ComponentType<FleetComponentProps>;
  localPosition: THREE.Vector3;
  fleetProp: Fleet;
}

interface RaycastResult {
  point: THREE.Vector3;
  normal: THREE.Vector3;
}

interface ExplosionEffect {
  id: string;
  position: THREE.Vector3;
}

// Constants
const COORDINATE_SCALE = 50;
const BASE_OFFSET = 0.01;
const RAY_ORIGIN_MULTIPLIER = 3;

export function Colony({ colony }: ColonyProps): React.JSX.Element {
  const { position, scale, rot, planetModelName, planetMainBase } = colony.planet;
  const colonyColor = colony.color;
  const planetGroupRef = useRef<THREE.Group | null>(null);
  const [basePosition, setBasePosition] = useState<THREE.Vector3 | null>(null);
  const [baseRotation, setBaseRotation] = useState<THREE.Quaternion | null>(null);
  const [placedStructures, setPlacedStructures] = useState<PlacedStructure[]>([]);
  const [placedFleets, setPlacedFleets] = useState<PlacedFleet[]>([]);
  const [placedOilPumps, setPlacedOilPumps] = useState<PlacedStructure[]>([]);
  const [placedSteelFactories, setPlacedSteelFactories] = useState<PlacedStructure[]>([]);
  const [explosions, setExplosions] = useState<ExplosionEffect[]>([]);
  const previousFleetsRef = useRef<Map<string, THREE.Vector3>>(new Map());

  // Unregister flag position on unmount
  useEffect(() => {
    return () => unregisterFlagPosition(colony.id);
  }, [colony.id]);

  // Define structures to be placed at the colony site.
  const colonyObjects: StructureConfig[] = useMemo(() => [
    {
      component: getBaseStructure(colony.colonyLevel),
      position: new THREE.Vector3(0, 0, 0),
    },
    {
      component: BaseFlag,
      position: new THREE.Vector3(0, 0, 1),
    }
  ], [colony.colonyLevel]);

  // Utility function to convert 2D coordinates to spherical direction
  const calculateSphericalDirection = useCallback((x: number, y: number): THREE.Vector3 => {
    const longitude = (x / COORDINATE_SCALE) * Math.PI * 2;
    const latitude = (y / COORDINATE_SCALE) * Math.PI;
    
    return new THREE.Vector3(
      Math.cos(latitude) * Math.cos(longitude),
      Math.sin(latitude),
      Math.cos(latitude) * Math.sin(longitude)
    ).normalize();
  }, []);

  // Utility function to setup planet mesh for raycasting
  const setupPlanetMesh = useCallback((planetGroup: THREE.Group): THREE.Mesh | null => {
    const planetMesh = planetGroup.getObjectByName('planet-surface') as THREE.Mesh;
    if (!planetMesh) return null;

    planetGroup.updateWorldMatrix(true, true);
    planetMesh.updateWorldMatrix(true, true);
    
    const geometry = planetMesh.geometry as THREE.BufferGeometry;
    if (geometry?.boundingSphere === null) {
      geometry.computeBoundingSphere();
    }
    
    return planetMesh;
  }, []);

  // Utility function to perform raycast from outside planet to surface
  const raycastToSurface = useCallback((
    planetGroup: THREE.Group,
    planetMesh: THREE.Mesh,
    direction: THREE.Vector3
  ): RaycastResult | null => {
    const planetCenter = new THREE.Vector3();
    planetGroup.getWorldPosition(planetCenter);

    const geometry = planetMesh.geometry as THREE.BufferGeometry;
    const boundingSphere = geometry?.boundingSphere;
    const radius = boundingSphere 
      ? boundingSphere.radius * Math.max(planetGroup.scale.x, planetGroup.scale.y, planetGroup.scale.z)
      : 1;

    const rayOrigin = planetCenter.clone().add(
      direction.clone().multiplyScalar(radius * RAY_ORIGIN_MULTIPLIER + 1)
    );
    const rayDirection = direction.clone().negate();

    const raycaster = new THREE.Raycaster(rayOrigin, rayDirection);
    const intersects = raycaster.intersectObject(planetMesh, true);

    if (intersects.length === 0) return null;

    const intersection = intersects[0];
    const normalMatrix = new THREE.Matrix3().getNormalMatrix(
      (intersection.object as THREE.Mesh).matrixWorld
    );
    
    const surfaceNormal = intersection.face
      ? intersection.face.normal.clone().applyMatrix3(normalMatrix).normalize()
      : direction.clone().negate();

    return {
      point: intersection.point.clone(),
      normal: surfaceNormal
    };
  }, []);

  // Utility function to transform local offset to world space
  const transformOffsetToWorldSpace = useCallback((
    localOffset: THREE.Vector3,
    basePosition: THREE.Vector3,
    baseRotation: THREE.Quaternion
  ): THREE.Vector3 => {
    const worldOffset = localOffset.clone().applyQuaternion(baseRotation);
    return basePosition.clone().add(worldOffset);
  }, []);

  // Utility function to combine rotations
  const combineRotations = useCallback((
    baseRotation: THREE.Quaternion,
    additionalRotation?: THREE.Euler
  ): THREE.Quaternion => {
    if (!additionalRotation) return baseRotation;
    const additionalQuaternion = new THREE.Quaternion().setFromEuler(additionalRotation);
    return baseRotation.clone().multiply(additionalQuaternion);
  }, []);

  const renderPlanetModel = () => {
    switch (planetModelName) {
      case 'Planet_A':
        return <PlanetA colonyColor={colonyColor} />;
      case 'Planet_B':
        return <PlanetB colonyColor={colonyColor} />;
      default:
        console.warn(`Unknown planet model: ${planetModelName}`);
        return <PlanetA colonyColor={colonyColor} />;
    }
  };

  // Map fleet types to components. Add more mappings here as new fleet components are created.
  const fleetComponentMap = useMemo(() => ({
    Attacker: FleetAttacker,
    Flanker: FleetAttacker,
    Fighter: FleetAttacker,
    Bomber: FleetAttacker,
    Scout: FleetAttacker,
  } as Record<string, React.ComponentType<FleetComponentProps>>), []);

  // Calculate base position and rotation on planet surface
  useEffect(() => {
    if (!planetGroupRef.current) return;

    const planetGroup = planetGroupRef.current;
    const planetMesh = setupPlanetMesh(planetGroup);
    
    if (!planetMesh) {
      const timeout = setTimeout(() => setBasePosition(null), 100);
      return () => clearTimeout(timeout);
    }

    const direction = calculateSphericalDirection(planetMainBase.x, planetMainBase.y);
    const raycastResult = raycastToSurface(planetGroup, planetMesh, direction);

    if (raycastResult) {
      const basePos = raycastResult.point.add(raycastResult.normal.clone().multiplyScalar(BASE_OFFSET));
      const baseQuat = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), raycastResult.normal);

      setBasePosition(basePos);
      setBaseRotation(baseQuat);
    } else {
      console.warn('Raycast missed planet surface — check mesh, transforms and material.side (use DoubleSide on model)');
    }
  }, [planetMainBase.x, planetMainBase.y, calculateSphericalDirection, setupPlanetMesh, raycastToSurface]);

  // Calculate positions for all colony structures
  useEffect(() => {
    if (!basePosition || !baseRotation || !planetGroupRef.current) return;

    const planetGroup = planetGroupRef.current;
    const planetMesh = setupPlanetMesh(planetGroup);
    
    if (!planetMesh) {
      console.warn('Planet surface mesh not ready for placing structures');
      return;
    }

    const planetCenter = new THREE.Vector3();
    planetGroup.getWorldPosition(planetCenter);

    const groupWorldQuat = new THREE.Quaternion();
    planetGroup.getWorldQuaternion(groupWorldQuat);

    const results: PlacedStructure[] = [];

    colonyObjects.forEach((obj) => {
      const approxWorld = transformOffsetToWorldSpace(obj.position, basePosition, baseRotation);
      const direction = approxWorld.clone().sub(planetCenter).normalize();
      const raycastResult = raycastToSurface(planetGroup, planetMesh, direction);

      if (raycastResult) {
        const quat = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), raycastResult.normal);
        const finalQuat = combineRotations(quat, obj.rotation);
        const localQuat = groupWorldQuat.clone().invert().multiply(finalQuat);
        
        // Get height offset with fallback to 0 for unknown colony levels
        const heightOffset = HEIGHT_OFFSET[colony.colonyLevel] ?? 0;
        const worldPos = raycastResult.point.add(raycastResult.normal.clone()
        .multiplyScalar(heightOffset));
        const localPos = planetGroup.worldToLocal(worldPos.clone());

        results.push({ 
          component: obj.component, 
          position: localPos, 
          quaternion: localQuat 
        });
      } else {
        console.warn('Raycast failed for object, using fallback position', obj);
      }
    });

    setPlacedStructures(results);

    // Register the flag's world position so attacking fleets can aim at it.
    // The flag is the second colony object (index 1).
    if (results.length > 1 && planetGroupRef.current) {
      const flagWorldPos = planetGroupRef.current.localToWorld(results[1].position.clone());
      registerFlagPosition(colony.id, flagWorldPos);
    }
  }, [
    basePosition, 
    baseRotation, 
    colonyObjects,
    colony.colonyLevel,
    colony.id,
    setupPlanetMesh, 
    raycastToSurface, 
    transformOffsetToWorldSpace, 
    combineRotations
  ]);

  // Calculate positions for oil pumps
  useEffect(() => {
    if (!planetGroupRef.current || !colony.planet.oilPumps || colony.planet.oilPumps.length === 0) {
      setPlacedOilPumps([]);
      return;
    }

    const planetGroup = planetGroupRef.current;
    const planetMesh = setupPlanetMesh(planetGroup);
    
    if (!planetMesh) {
      console.warn('Planet surface mesh not ready for placing oil pumps');
      return;
    }

    const planetCenter = new THREE.Vector3();
    planetGroup.getWorldPosition(planetCenter);

    const groupWorldQuat = new THREE.Quaternion();
    planetGroup.getWorldQuaternion(groupWorldQuat);

    const results: PlacedStructure[] = [];

    colony.planet.oilPumps.forEach((pump) => {
      const direction = calculateSphericalDirection(pump.position.x, pump.position.y);
      const raycastResult = raycastToSurface(planetGroup, planetMesh, direction);

      if (raycastResult) {
        const quat = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), raycastResult.normal);
        const localQuat = groupWorldQuat.clone().invert().multiply(quat);
        
        const worldPos = raycastResult.point.add(raycastResult.normal.clone().multiplyScalar(BASE_OFFSET));
        const localPos = planetGroup.worldToLocal(worldPos.clone());

        results.push({ 
          component: OilPump, 
          position: localPos, 
          quaternion: localQuat 
        });
      } else {
        console.warn('Raycast failed for oil pump', pump);
      }
    });

    setPlacedOilPumps(results);
  }, [
    colony.planet.oilPumps,
    setupPlanetMesh,
    raycastToSurface,
    calculateSphericalDirection
  ]);

  // Calculate positions for steel factories
  useEffect(() => {
    if (!planetGroupRef.current || !colony.planet.steelFactories || colony.planet.steelFactories.length === 0) {
      setPlacedSteelFactories([]);
      return;
    }

    const planetGroup = planetGroupRef.current;
    const planetMesh = setupPlanetMesh(planetGroup);
    
    if (!planetMesh) {
      console.warn('Planet surface mesh not ready for placing steel factories');
      return;
    }

    const planetCenter = new THREE.Vector3();
    planetGroup.getWorldPosition(planetCenter);

    const groupWorldQuat = new THREE.Quaternion();
    planetGroup.getWorldQuaternion(groupWorldQuat);

    const results: PlacedStructure[] = [];

    colony.planet.steelFactories.forEach((factory) => {
      const direction = calculateSphericalDirection(factory.position.x, factory.position.y);
      const raycastResult = raycastToSurface(planetGroup, planetMesh, direction);

      if (raycastResult) {
        const quat = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), raycastResult.normal);
        const localQuat = groupWorldQuat.clone().invert().multiply(quat);
        
        const worldPos = raycastResult.point.add(raycastResult.normal.clone().multiplyScalar(BASE_OFFSET));
        const localPos = planetGroup.worldToLocal(worldPos.clone());

        results.push({ 
          component: SteelFactory, 
          position: localPos, 
          quaternion: localQuat 
        });
      } else {
        console.warn('Raycast failed for steel factory', factory);
      }
    });

    setPlacedSteelFactories(results);
  }, [
    colony.planet.steelFactories,
    setupPlanetMesh,
    raycastToSurface,
    calculateSphericalDirection
  ]);

  // Calculate local positions for fleets and select the correct component for each fleet type
  useEffect(() => {
    if (!planetGroupRef.current || !basePosition || !baseRotation) return;
    if (!colony.colonyFleet || colony.colonyFleet.length === 0) {
      setPlacedFleets([]);
      return;
    }

    const results: PlacedFleet[] = [];

    // The fleet wrapper group has planetInverseRotation, which cancels the planet's
    // rotation. Its effective world transform is: T(planetPos) * S(scale).
    // So wrapper-local coords = (worldPos - planetPos) / scale.
    // We must convert positions/velocities/waypoints to this wrapper-local space,
    // NOT to the planet-local space (which includes rotation).
    const planetPos = new THREE.Vector3(position.x, position.y, position.z);

    colony.colonyFleet.forEach((fleet) => {
      const comp = fleetComponentMap[fleet.type] ?? FleetAttacker;

      // The fleet container should be at the planet origin, because fleet.position
      // (converted to local space) is relative to the planet center.
      const localPos = new THREE.Vector3(0, 0, 0);
      
      // Convert world space position to wrapper-local space for rendering
      // wrapper-local = (worldPos - planetPos) / scale
      const worldFleetPos = new THREE.Vector3(fleet.position.x, fleet.position.y, fleet.position.z);
      const localFleetPos = worldFleetPos.clone().sub(planetPos).divideScalar(scale);
      
      // Convert world space velocity to wrapper-local space
      // Since wrapper has no rotation, velocity just needs scale adjustment
      const worldVelocity = new THREE.Vector3(fleet.velocity.x, fleet.velocity.y, fleet.velocity.z);
      const localVelocity = worldVelocity.clone().divideScalar(scale);
      
      const localFleetProp: Fleet = { 
        ...fleet, 
        position: { x: localFleetPos.x, y: localFleetPos.y, z: localFleetPos.z },
        velocity: { x: localVelocity.x, y: localVelocity.y, z: localVelocity.z },
        // Also convert waypoints to wrapper-local space if they exist
        waypoints: fleet.waypoints?.map(wp => {
          const worldWP = new THREE.Vector3(wp.x, wp.y, wp.z);
          const localWP = worldWP.clone().sub(planetPos).divideScalar(scale);
          return { x: localWP.x, y: localWP.y, z: localWP.z };
        })
      };

      // Override target position with the actual rendered flag world position
      // so projectiles aim at the visible flag, not the backend's approximation.
      if (localFleetProp.target?.id) {
        const actualFlagPos = getFlagPosition(localFleetProp.target.id);
        if (actualFlagPos) {
          localFleetProp.target = {
            ...localFleetProp.target,
            position: { x: actualFlagPos.x, y: actualFlagPos.y, z: actualFlagPos.z }
          };
        }
      }

      results.push({ component: comp, localPosition: localPos, fleetProp: localFleetProp });
    });

    setPlacedFleets(results);
    
    // Track fleet removals and create explosions
    const currentFleetIds = new Set(colony.colonyFleet.map(f => f.id));
    const previousFleets = previousFleetsRef.current;
    
    // Check for removed fleets
    previousFleets.forEach((worldPos, fleetId) => {
      if (!currentFleetIds.has(fleetId)) {
        // Fleet was removed - create explosion at its last known world position
        setExplosions(prev => [...prev, {
          id: `explosion-${fleetId}-${Date.now()}`,
          position: worldPos.clone()
        }]);
      }
    });
    
    // Update previous fleets map with current fleet positions (in world space)
    const newPreviousFleets = new Map<string, THREE.Vector3>();
    colony.colonyFleet.forEach(fleet => {
      newPreviousFleets.set(fleet.id, new THREE.Vector3(fleet.position.x, fleet.position.y, fleet.position.z));
    });
    previousFleetsRef.current = newPreviousFleets;
  }, [colony.colonyFleet, fleetComponentMap, basePosition, baseRotation, position.x, position.y, position.z, scale]);

  // Calculate the inverse of the planet's rotation to keep fleets upright
  const planetInverseRotation = useMemo(() => {
    const planetQuat = new THREE.Quaternion();
    planetQuat.setFromEuler(new THREE.Euler(rot.x, rot.y, rot.z));
    return planetQuat.invert();
  }, [rot.x, rot.y, rot.z]);

  return (
    <>
    <group
      ref={planetGroupRef}
      position={[position.x, position.y, position.z]}
      scale={scale}
      rotation={[rot.x, rot.y, rot.z]}
    >
      {renderPlanetModel()}

      {/* Colony Structures placed via raycast */}
      {placedStructures.map((structure, index) => {
        const Component = structure.component;
        const { position: p, quaternion: q } = structure;
        return (
          <group 
            key={index} 
            position={[p.x, p.y, p.z]} 
            quaternion={[q.x, q.y, q.z, q.w]}
          >
            <Component colonyColor={colonyColor} />
            {index === 0 && (
                <BaseDefenseSystem 
                    isAttacking={colony.is_fighting} 
                    targetPos={colony.defense_target_pos} 
                />
            )}
          </group>
        );
      })}

      {/* Oil Pumps placed via raycast */}
      {placedOilPumps.map((pump, index) => {
        const Component = pump.component;
        const { position: p, quaternion: q } = pump;
        return (
          <group 
            key={`oil-pump-${index}`} 
            position={[p.x, p.y, p.z]} 
            quaternion={[q.x, q.y, q.z, q.w]}
          >
            <Component colonyColor={colonyColor} />
          </group>
        );
      })}

      {/* Steel Factories placed via raycast */}
      {placedSteelFactories.map((factory, index) => {
        const Component = factory.component;
        const { position: p, quaternion: q } = factory;
        return (
          <group 
            key={`steel-factory-${index}`} 
            position={[p.x, p.y, p.z]} 
            quaternion={[q.x, q.y, q.z, q.w]}
          >
            <Component colonyColor={colonyColor} />
          </group>
        );
      })}

      {/* Fleets rendered via mapped components */}
      {placedFleets.map((pf, idx) => {
        const FleetComp = pf.component;
        return (
          <group 
            key={`fleet-${pf.fleetProp.id}-${idx}`} 
            position={[pf.localPosition.x, pf.localPosition.y, pf.localPosition.z]}
            quaternion={[planetInverseRotation.x, planetInverseRotation.y, planetInverseRotation.z, planetInverseRotation.w]}>
            <FleetComp colonyColor={colonyColor} fleetProp={pf.fleetProp} onUpdate={() => { /* noop for now */ }} />
          </group>
        );
      })}
    </group>
    
    {/* Explosion effects - rendered outside planet group in world space */}
    <>
      {explosions.map((explosion) => (
        <FleetExplosion
          key={explosion.id}
          position={explosion.position}
          onComplete={() => {
            // Remove explosion after it completes
            setExplosions(prev => prev.filter(e => e.id !== explosion.id));
          }}
        />
      ))}
    </>
    </>
  );
}