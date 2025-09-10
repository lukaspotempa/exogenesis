import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import * as THREE from 'three';
import type { Colony as ColonyType } from '../../types/Types';
import { PlanetA } from './planets/PlanetA';
import { ColonyBaseSmall } from './structures/ColonyBaseSmall';
import { BaseFlag } from './structures/BaseFlag';

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

interface RaycastResult {
  point: THREE.Vector3;
  normal: THREE.Vector3;
}

// Constants
const COORDINATE_SCALE = 50;
const BASE_OFFSET = 0.01;
const STRUCTURE_Y_OFFSET = -0.02;
const RAY_ORIGIN_MULTIPLIER = 3;

export function Colony({ colony }: ColonyProps): React.JSX.Element {
  const { position, scale, rot, planetModelName, planetMainBase } = colony.planet;
  const colonyColor = colony.color;
  const planetGroupRef = useRef<THREE.Group | null>(null);
  const [basePosition, setBasePosition] = useState<THREE.Vector3 | null>(null);
  const [baseRotation, setBaseRotation] = useState<THREE.Quaternion | null>(null);
  const [placedStructures, setPlacedStructures] = useState<PlacedStructure[]>([]);

  // Define structures to be placed at the colony site.
  const colonyObjects: StructureConfig[] = useMemo(() => [
    {
      component: ColonyBaseSmall,
      position: new THREE.Vector3(0, 0, 0),
    },
    {
      component: BaseFlag,
      position: new THREE.Vector3(0, 0, 1),
    }
  ], []);

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
      default:
        console.warn(`Unknown planet model: ${planetModelName}`);
        return <PlanetA colonyColor={colonyColor} />;
    }
  };

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

        const worldPos = raycastResult.point.add(raycastResult.normal.clone().multiplyScalar(BASE_OFFSET));
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
    setupPlanetMesh, 
    raycastToSurface, 
    transformOffsetToWorldSpace, 
    combineRotations
  ]);

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
            position={[p.x, p.y + STRUCTURE_Y_OFFSET, p.z]} 
            quaternion={[q.x, q.y, q.z, q.w]}
          >
            <Component colonyColor={colonyColor} />
          </group>
        );
      })}
    </group>
  );
}