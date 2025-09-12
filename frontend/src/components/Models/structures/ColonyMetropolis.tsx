import React from 'react';
import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface BaseSmallGLTF extends GLTF {
  nodes: {
    "group1872301862": Mesh;
  };
  materials: {
    PaletteMaterial001: MeshStandardMaterial;
  };
}

interface Props {
  colonyColor?: string;
}

const ColonyMetropolis = ({ colonyColor }: { colonyColor?: string }): React.JSX.Element => {
  // call hook unconditionally to satisfy React Hook rules
  const gltf = useGLTF('/models/structures/Urban Park v1-transformed.glb') as unknown as Partial<BaseSmallGLTF>;
  const nodes = gltf.nodes as BaseSmallGLTF['nodes'] | undefined;
  const materials = gltf.materials as BaseSmallGLTF['materials'] | undefined;

  // If model data isn't available yet, render a simple fallback
  if (!nodes?.group1872301862 || !materials?.PaletteMaterial001) {
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
        geometry={nodes.group1872301862.geometry} 
        receiveShadow
        castShadow
        material={materials.PaletteMaterial001}
        scale={3}
      >
      </mesh>
    </group>
  );
}

useGLTF.preload('/models/structures/Urban Park v1-transformed.glb');

ColonyMetropolis.displayName = 'ColonyMetropolis';
export { ColonyMetropolis };