import React from 'react';
import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface OilPumpGLTF extends GLTF {
  nodes: {
    "Object001_Material_#73_0": Mesh;
  };
  materials: {
    Material_73: MeshStandardMaterial;
  };
}

const OilPump = ({ colonyColor }: { colonyColor?: string }): React.JSX.Element => {
  // call hook unconditionally to satisfy React Hook rules
  const gltf = useGLTF('/models/structures/pump_jack-transformed.glb') as unknown as Partial<OilPumpGLTF>;
  const nodes = gltf.nodes as OilPumpGLTF['nodes'] | undefined;
  const materials = gltf.materials as OilPumpGLTF['materials'] | undefined;

  // If model data isn't available yet, render a simple fallback
  console.log(nodes)
  if (!nodes || !nodes["Object001_Material_#73_0"] || !materials?.Material_73) {
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
        geometry={nodes["Object001_Material_#73_0"].geometry} 
        receiveShadow
        castShadow
        material={materials.Material_73}
        scale={0.001}
        position={[0, 0.1, 0]}
      >
      </mesh>
    </group>
  );
}

useGLTF.preload('/models/structures/pump_jack-transformed.glb');

OilPump.displayName = 'OilPump';
export { OilPump };