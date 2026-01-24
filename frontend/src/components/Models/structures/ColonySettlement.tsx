import React from 'react';
import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface ColonySettlement extends GLTF {
  nodes: {
    "basemodule_A": Mesh;
  };
  materials: {
    spacebits_texture: MeshStandardMaterial;
  };
}

const ColonySettlement = ({ colonyColor }: { colonyColor?: string }): React.JSX.Element => {
  // call hook unconditionally to satisfy React Hook rules
  const gltf = useGLTF('/models/structures/Space Base Modules-transformed.glb') as unknown as Partial<ColonySettlement>;
  const nodes = gltf.nodes as ColonySettlement['nodes'] | undefined;
  const materials = gltf.materials as ColonySettlement['materials'] | undefined;

  // If model data isn't available yet, render a simple fallback
  if (!nodes?.basemodule_A || !materials?.spacebits_texture) {
    console.error('Base model nodes/materials not available, rendering fallback');
    return (
      <group dispose={null}>
        <mesh scale={0.2}>
          <boxGeometry args={[1, 0.5, 1]} />
          <meshStandardMaterial color={colonyColor || '#888888'} />
        </mesh>
      </group>
    );
  }

  return (
    <group dispose={null}>
      <mesh 
        geometry={nodes.basemodule_A.geometry} 
        receiveShadow
        castShadow
        material={materials.spacebits_texture}
        scale={25}
        position={[-1, 0,0]}
      >
      </mesh>
    </group>
  );
}

useGLTF.preload('/models/structures/Space Base Modules-transformed.glb');

ColonySettlement.displayName = 'ColonySettlement';
export { ColonySettlement };