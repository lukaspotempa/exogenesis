import React, { useEffect, useState } from 'react';
import type { Colony } from '../../types/Types';
import { coloniesStore } from '../../store/coloniesStore';
import { Planet } from '../Models/Planet';
import { Ship1 } from '../Models/Ship_1';

export function MainScene(): React.JSX.Element {
  const [colonies, setColonies] = useState<Colony[]>([]);

  useEffect(() => {
    // Subscribe to store changes
    const unsubscribe = coloniesStore.subscribe(() => {
      setColonies(coloniesStore.getColonies());
    });

    // Initial load
    setColonies(coloniesStore.getColonies());

    return unsubscribe;
  }, []);

  return (
    <group>
      {/* Render all colony planets */}
      {colonies.map((colony, index) => (
        <Planet 
          key={`${colony.name}-${index}`}
          planet={colony.planet}
          colonyColor={colony.color}
        />
      ))}

      <Ship1 />

      {/* Reference cube */}
      <mesh position={[2, 0, 0]} scale={0.5}>
        <boxGeometry />
        <meshStandardMaterial color="hotpink" />
      </mesh>

      <ambientLight intensity={0.6} />
      <directionalLight
        position={[10, 10, 5]}
        intensity={1}
        castShadow
        shadow-mapSize={2048}
      />
      <pointLight position={[-10, -10, -10]} intensity={0.5} />
      <hemisphereLight args={[0xffffbb, 0x080820, 0.3]} />
    </group>
  );
}