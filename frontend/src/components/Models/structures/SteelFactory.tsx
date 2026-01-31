import React from 'react';
import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface SteelFactoryGLTF extends GLTF {
  nodes: {
    Factory: Mesh;
  };
  materials: {
    Mat: MeshStandardMaterial;
  };
}

const SteelFactory = ({ colonyColor }: { colonyColor?: string }): React.JSX.Element => {
  // call hook unconditionally to satisfy React Hook rules
  const gltf = useGLTF('/models/structures/Factory-transformed.glb') as unknown as Partial<SteelFactoryGLTF>;
  const nodes = gltf.nodes as SteelFactoryGLTF['nodes'] | undefined;
  const materials = gltf.materials as SteelFactoryGLTF['materials'] | undefined;

  // If model data isn't available yet, render a simple fallback
  if (!nodes || !nodes["Factory"] || !materials?.Mat) {
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
        geometry={nodes.Factory.geometry} 
        receiveShadow
        castShadow
        material={materials.Mat}
        scale={0.005} 
        position={[0, 0, 0]}
      >
      </mesh>
    </group>
  );
}

useGLTF.preload('/models/structures/Factory-transformed.glb');

SteelFactory.displayName = 'Steel Factory';
export { SteelFactory };