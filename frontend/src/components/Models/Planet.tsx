import React, { useRef, useEffect, useState } from 'react';
import * as THREE from 'three';
import type { Planet as PlanetType } from '../../types/Types';
import { PlanetA } from './planets/PlanetA';
import { ColonyBaseSmall } from './structures/ColonyBaseSmall';

interface PlanetProps {
  planet: PlanetType;
  colonyColor?: string;
}

export function Planet({ planet, colonyColor }: PlanetProps): React.JSX.Element {
  const { position, scale, rot, planetModelName, planetMainBase } = planet;
  const planetGroupRef = useRef<THREE.Group>(null);
  const [basePosition, setBasePosition] = useState<THREE.Vector3 | null>(null);
  const [baseRotation, setBaseRotation] = useState<THREE.Quaternion | null>(null);

  const renderPlanetModel = () => {
    switch (planetModelName) {
      case 'Planet_A':
        return <PlanetA colonyColor={colonyColor} />;
      default:
        console.warn(`Unknown planet model: ${planetModelName}`);
        return <PlanetA colonyColor={colonyColor} />;
    }
  };



  // Calculate surface position using raycast to actual geometry
  useEffect(() => {
    if (!planetGroupRef.current) return;

    // Convert 2D coordinates to spherical coordinates for direction
    const longitude = (planetMainBase.x / 50) * Math.PI * 2; // Full rotation
    const latitude = (planetMainBase.y / 50) * Math.PI; // Half rotation for latitude

    // Create direction vector from planet center outward
    const direction = new THREE.Vector3(
      Math.cos(latitude) * Math.cos(longitude),
      Math.sin(latitude),
      Math.cos(latitude) * Math.sin(longitude)
    ).normalize();

    // Find the planet surface mesh for raycasting
    const planetMesh = planetGroupRef.current.getObjectByName('planet-surface') as THREE.Mesh;

    if (planetMesh) {
      // Create raycaster from far outside the planet toward center
      const raycaster = new THREE.Raycaster();
      const rayOrigin = direction.clone().multiplyScalar(1000); // Start far outside
      const rayDirection = direction.clone().negate(); // Point toward center

      raycaster.set(rayOrigin, rayDirection);

      // Perform raycast
      const intersects = raycaster.intersectObject(planetMesh, false);

      if (intersects.length > 0) {
        const intersection = intersects[0];
        const surfacePoint = intersection.point;
        const surfaceNormal = intersection.face?.normal || direction;

        // Apply small offset above surface
        const baseOffset = 0.1;
        const basePosition = surfacePoint.clone().add(surfaceNormal.clone().multiplyScalar(baseOffset));

        // Calculate rotation to align base with surface normal
        const quaternion = new THREE.Quaternion();
        quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), surfaceNormal);

        setBasePosition(basePosition);
        setBaseRotation(quaternion);

        console.log('Base placed via raycast at:', basePosition, 'surface normal:', surfaceNormal);
      } else {
        console.warn('Raycast failed to hit planet surface');
      }
    } else {
      // Fallback: try again after a short delay if mesh not ready
      const timeout = setTimeout(() => {
        // Trigger re-run of this effect
        setBasePosition(null);
      }, 100);

      return () => clearTimeout(timeout);
    }
  }, [planetMainBase.x, planetMainBase.y, planetGroupRef.current]);

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



      {/* Colony Base */}
      {basePosition && baseRotation && (
        <group
          position={[basePosition.x, basePosition.y, basePosition.z]}
          quaternion={[baseRotation.x, baseRotation.y, baseRotation.z, baseRotation.w]}
        >
          <ColonyBaseSmall colonyColor={colonyColor} />

          {/* Debug marker */}

        </group>
      )}

    </group>
  );
}