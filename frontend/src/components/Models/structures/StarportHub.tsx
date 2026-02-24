import React from 'react';
import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface StarportHubGLTF extends GLTF {
  nodes: {
    "group1872301862": Mesh;
  };
  materials: {
    PaletteMaterial001: MeshStandardMaterial;
  };
}

const StarportHub = ({ colonyColor }: { colonyColor?: string }): React.JSX.Element => {
  // call hook unconditionally to satisfy React Hook rules
  const gltf = useGLTF('/models/structures/Urban Park v1-transformed.glb') as unknown as Partial<StarportHubGLTF>;
  const nodes = gltf.nodes as StarportHubGLTF['nodes'] | undefined;
  const materials = gltf.materials as StarportHubGLTF['materials'] | undefined;

  // If model data isn't available yet, render a simple fallback
  if (!nodes?.group1872301862 || !materials?.PaletteMaterial001) {
    console.error('Starport Hub model nodes/materials not available, rendering fallback');
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
        geometry={nodes.group1872301862.geometry}
        receiveShadow
        castShadow
        material={materials.PaletteMaterial001}
        scale={3}
      />
    </group>
  );
};

useGLTF.preload('/models/structures/Urban Park v1-transformed.glb');

StarportHub.displayName = 'StarportHub';
export { StarportHub };
