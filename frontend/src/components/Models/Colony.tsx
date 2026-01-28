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

// Map colony levels to their corresponding base structure components
const COLONY_BASE_STRUCTURES: Record<ColonyLevel, React.ComponentType<{ colonyColor?: string }>> = {
  'Colony': ColonyBaseSmall,
  'Settlement': ColonySettlement,
  'Township': ColonyMetropolis,
  'Metropolis': ColonyMetropolis,
  'Starport Hub': ColonyMetropolis,
};

const HEIGHT_OFFSET: Record<string, number> = {
  'Colony': -0.03,
  'Settlement': -0.05,
  'Township': 0.35,
  'Metropolis': 0.35,
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
    Flanker: FleetAttacker,  // Flankers use the same component, formation handled by count
    // Fighter: FleetFighter,
    // Bomber: FleetBomber,
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
  }, [
    basePosition, 
    baseRotation, 
    colonyObjects,
    colony.colonyLevel,
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

  // Calculate local positions for fleets and select the correct component for each fleet type
  useEffect(() => {
    if (!planetGroupRef.current || !basePosition || !baseRotation) return;
    if (!colony.colonyFleet || colony.colonyFleet.length === 0) {
      setPlacedFleets([]);
      return;
    }

    const planetGroup = planetGroupRef.current;
    const results: PlacedFleet[] = [];

    // Get the surface normal at the base position
    const planetCenter = new THREE.Vector3();
    planetGroup.getWorldPosition(planetCenter);
    const surfaceNormal = basePosition.clone().sub(planetCenter).normalize();
    
    // Spawn height for fleets above the base
    const fleetSpawnHeight = 3.0;

    colony.colonyFleet.forEach((fleet) => {
      const comp = fleetComponentMap[fleet.type] ?? FleetAttacker;

      // Position fleet above the colony base along the surface normal
      const fleetWorldPos = basePosition.clone().add(surfaceNormal.clone().multiplyScalar(fleetSpawnHeight));
      const localPos = planetGroup.worldToLocal(fleetWorldPos.clone());
      
      // Pass the fleet as-is - the fleet component will handle rendering multiple ships
      // based on fleet.count in the correct formation
      const localFleetProp: Fleet = { ...fleet, position: { x: 0, y: 0, z: 0 } };

      results.push({ component: comp, localPosition: localPos, fleetProp: localFleetProp });
    });

    setPlacedFleets(results);
  }, [colony.colonyFleet, fleetComponentMap, basePosition, baseRotation]);

  // Calculate the inverse of the planet's rotation to keep fleets upright
  const planetInverseRotation = useMemo(() => {
    const planetQuat = new THREE.Quaternion();
    planetQuat.setFromEuler(new THREE.Euler(rot.x, rot.y, rot.z));
    return planetQuat.invert();
  }, [rot.x, rot.y, rot.z]);

  return (
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
  );
}