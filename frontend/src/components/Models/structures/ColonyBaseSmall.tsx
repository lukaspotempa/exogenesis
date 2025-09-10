import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface BaseSmallGLTF extends GLTF {
  nodes: {
    Base_Large: Mesh;
  };
  materials: {
    Atlas: MeshStandardMaterial;
  };
}

interface Props {
  colonyColor?: string;
}

export function ColonyBaseSmall({ colonyColor }: Props): React.JSX.Element {
  // call hook unconditionally to satisfy React Hook rules
  const gltf = useGLTF('/models/structures/Base_Small-transformed.glb') as unknown as Partial<BaseSmallGLTF>;
  const nodes = gltf.nodes as BaseSmallGLTF['nodes'] | undefined;
  const materials = gltf.materials as BaseSmallGLTF['materials'] | undefined;

  // If model data isn't available yet, render a simple fallback
  if (!nodes?.Base_Large || !materials?.Atlas) {
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
        geometry={nodes.Base_Large.geometry} 
        receiveShadow
        castShadow
        material={materials.Atlas}
        scale={5}
      >
      </mesh>
    </group>
  );
}

useGLTF.preload('/models/structures/Base_Small-transformed.glb');