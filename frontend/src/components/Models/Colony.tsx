import React, { useRef, useEffect, useState, useMemo } from 'react';
import * as THREE from 'three';
import type { Planet as PlanetType } from '../../types/Types';
import { PlanetA } from './planets/PlanetA';
import { ColonyBaseSmall } from './structures/ColonyBaseSmall';
import { BaseFlag } from './structures/BaseFlag';

interface PlanetProps {
  planet: PlanetType;
  colonyColor?: string;
}

interface StructureConfig {
  component: React.ComponentType<{ colonyColor?: string }>;
  // position and rotation are local, relative to the base position/orientation
  position: THREE.Vector3; // Local position relative to basePosition
  rotation?: THREE.Euler; // Local rotation relative to baseOrientation (applied after aligning to surface normal)
}

export function Planet({ planet, colonyColor }: PlanetProps): React.JSX.Element {
  const { position, scale, rot, planetModelName, planetMainBase } = planet;
  const planetGroupRef = useRef<THREE.Group | null>(null);
  const [basePosition, setBasePosition] = useState<THREE.Vector3 | null>(null);
  const [baseRotation, setBaseRotation] = useState<THREE.Quaternion | null>(null);
  const [placedStructures, setPlacedStructures] = useState<Array<{
    component: React.ComponentType<{ colonyColor?: string }>;
    position: THREE.Vector3;
    quaternion: THREE.Quaternion;
  }>>([]);

  // Define structures to be placed at the colony site.
  // position/rotation are local relative to the base (tangent plane of the surface at base).
  const colonyObjects: StructureConfig[] = useMemo<StructureConfig[]>(() => [
    {
      component: ColonyBaseSmall,
      position: new THREE.Vector3(0, 0, 0), // Base at the exact surface position
    },
    {
      component: BaseFlag,
      position: new THREE.Vector3(0.02, 0, 0.5),
    }
  ], []);

  const renderPlanetModel = () => {
    switch (planetModelName) {
      case 'Planet_A':
        return <PlanetA colonyColor={colonyColor} />;
      default:
        console.warn(`Unknown planet model: ${planetModelName}`);
        return <PlanetA colonyColor={colonyColor} />;
    }
  };

  useEffect(() => {
    if (!planetGroupRef.current) return;
    console.log("Planet Group Ref: ", planetGroupRef)

    // Convert 2D coordinates to spherical coordinates for direction
    const longitude = (planetMainBase.x / 50) * Math.PI * 2; // Full rotation
    const latitude = (planetMainBase.y / 50) * Math.PI; // Half rotation for latitude

    // Create direction vector from planet center outward (local sphere direction)
    const localDirection = new THREE.Vector3(
      Math.cos(latitude) * Math.cos(longitude),
      Math.sin(latitude),
      Math.cos(latitude) * Math.sin(longitude)
    ).normalize();

    // Find the planet surface mesh for raycasting
    const planetMesh = planetGroupRef.current.getObjectByName('planet-surface') as THREE.Mesh;
    if (!planetMesh) {
      // mesh not ready — try again shortly
      const timeout = setTimeout(() => setBasePosition(null), 100);
      return () => clearTimeout(timeout);
    }

    // Ensure transforms / world matrices & bounds are current
    planetGroupRef.current.updateWorldMatrix(true, true);
    planetMesh.updateWorldMatrix(true, true);
    // geometry is BufferGeometry for GLTF meshes
    const geometry = planetMesh.geometry as THREE.BufferGeometry | undefined;
    if (geometry && geometry.boundingSphere === null) {
      geometry.computeBoundingSphere();
    }

    // planet center in world space
    const planetCenter = new THREE.Vector3();
    planetGroupRef.current.getWorldPosition(planetCenter);

    // compute a safe radius to place the ray origin well outside the mesh
    const bs = geometry ? geometry.boundingSphere : null;
    const radius = bs ? bs.radius * Math.max(planetGroupRef.current.scale.x || 1, planetGroupRef.current.scale.y || 1, planetGroupRef.current.scale.z || 1) : 1;
    const rayOrigin = planetCenter.clone().add(localDirection.clone().multiplyScalar(radius * 3 + 1)); // outside the planet
    const rayDirection = localDirection.clone().negate(); // point toward planet center

    /* DEBUG ARROWS
    const arrow = new THREE.ArrowHelper(rayDirection, rayOrigin, radius * 2, 0xff0000);
    (planetGroupRef.current.parent || planetGroupRef.current).add(arrow);*/

    const raycaster = new THREE.Raycaster(rayOrigin, rayDirection);

    // Use recursive=true in case the surface is nested under the named object
    const intersects = raycaster.intersectObject(planetMesh, true);

    if (intersects.length > 0) {
      const intersection = intersects[0];

      // convert face normal to world space
      const normalMatrix = new THREE.Matrix3().getNormalMatrix((intersection.object as THREE.Mesh).matrixWorld);
      const surfaceNormal = intersection.face
        ? intersection.face.normal.clone().applyMatrix3(normalMatrix).normalize()
        : localDirection.clone().negate();

      const surfacePoint = intersection.point.clone();
      const baseOffset = 0.01;
      const computedBasePosition = surfacePoint.add(surfaceNormal.clone().multiplyScalar(baseOffset));

      const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), surfaceNormal);

      setBasePosition(computedBasePosition);
      setBaseRotation(quaternion);
    } else {
      console.warn('Raycast missed planet surface — check mesh, transforms and material.side (use DoubleSide on model)');
    }
  }, [planetMainBase.x, planetMainBase.y]);

  // Helper function to transform local offset to world space
  const transformOffsetToWorldSpace = (
    localOffset: THREE.Vector3,
    basePosition: THREE.Vector3,
    baseRotation: THREE.Quaternion
  ): THREE.Vector3 => {
    const worldOffset = localOffset.clone().applyQuaternion(baseRotation);
    return basePosition.clone().add(worldOffset);
  };

  // Helper function to combine rotations
  const combineRotations = (
    baseRotation: THREE.Quaternion,
    additionalRotation?: THREE.Euler
  ): THREE.Quaternion => {
    if (!additionalRotation) return baseRotation;

    const additionalQuaternion = new THREE.Quaternion().setFromEuler(additionalRotation);
    return baseRotation.clone().multiply(additionalQuaternion);
  };

  // When we have a basePosition and rotation, compute final positions/quaternions for each object
  useEffect(() => {
    if (!basePosition || !baseRotation || !planetGroupRef.current) return;

    const planetMesh = planetGroupRef.current.getObjectByName('planet-surface') as THREE.Mesh;
    if (!planetMesh) {
      console.warn('Planet surface mesh not ready for placing structures');
      return;
    }

    const planetCenter = new THREE.Vector3();
    planetGroupRef.current.getWorldPosition(planetCenter);

    const raycaster = new THREE.Raycaster();

    const results: Array<{ component: React.ComponentType<{ colonyColor?: string }>; position: THREE.Vector3; quaternion: THREE.Quaternion }> = [];

    const groupWorldQuat = new THREE.Quaternion();
    planetGroupRef.current.getWorldQuaternion(groupWorldQuat);

    colonyObjects.forEach((obj) => {
      // Compute approximate world-space target by applying base rotation to the object's local position
      const approxWorld = transformOffsetToWorldSpace(obj.position, basePosition, baseRotation);

      // Direction from planet center through approxWorld
      const direction = approxWorld.clone().sub(planetCenter).normalize();

      const rayOrigin = planetCenter.clone().add(direction.clone().multiplyScalar(1000));
      const rayDirection = direction.clone().negate();
      raycaster.set(rayOrigin, rayDirection);

      // Use recursive=true in case the surface mesh is nested under group nodes
      const intersects = raycaster.intersectObject(planetMesh, true);

      if (intersects.length > 0) {
        const intersection = intersects[0];
        const surfacePoint = intersection.point.clone();

        // Convert the face normal to world space
        let surfaceNormal = direction.clone();
        if (intersection.face) {
          const normalMatrix = new THREE.Matrix3().getNormalMatrix(planetMesh.matrixWorld);
          surfaceNormal = intersection.face.normal.clone().applyMatrix3(normalMatrix).normalize();
        }

        const quat = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), surfaceNormal);

        // Apply additional local rotation if provided
        const finalQuat = combineRotations(quat, obj.rotation);

        // Convert finalQuat (world-space) into planet group's local quaternion
        const localQuat = groupWorldQuat.clone().invert().multiply(finalQuat);

        // Convert the computed world-space surface point to the planet group's local space
        const worldPos = surfacePoint.add(surfaceNormal.clone().multiplyScalar(0.01));
        const localPos = planetGroupRef.current!.worldToLocal(worldPos.clone());

        results.push({ component: obj.component, position: localPos, quaternion: localQuat });
      } else {
        console.warn('Raycast failed for object, using fallback approxWorld position', obj);
      }
    });

    setPlacedStructures(results);
  }, [basePosition, baseRotation, colonyObjects]);

  // Debug logging
  useEffect(() => {
    console.log('Planet render - Base coordinates:', planetMainBase, 'Position:', basePosition, 'Rotation:', baseRotation);
  }, [planetMainBase, basePosition, baseRotation]);

  return (
    <group
      ref={planetGroupRef}
      position={[position.x, position.y, position.z]}
      scale={scale}
      rotation={[rot.x, rot.y, rot.z]}
    >
      {renderPlanetModel()}

      {/* Colony Structures placed via raycast */}
      {placedStructures.map((s, index) => {
        const Component = s.component;
        const q = s.quaternion;
        const p = s.position;
        return (
          <group key={index} position={[p.x, p.y - 0.02, p.z]} quaternion={[q.x, q.y, q.z, q.w]}>
            <Component colonyColor={colonyColor} />
          </group>
        );
      })}
    </group>
  );
}