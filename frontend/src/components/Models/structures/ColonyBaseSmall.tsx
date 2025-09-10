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
  try {
    const { nodes, materials } = useGLTF('/models/structures/Base_Small-transformed.glb') as unknown as BaseSmallGLTF;
    return (
      <group dispose={null}>
        {/* The actual base model */}
        <mesh 
          geometry={nodes.Base_Large.geometry} 
          receiveShadow
          castShadow
          material={materials.Atlas}
          scale={[5, 5, 5]}
        >
          <meshStandardMaterial 
            color={colonyColor || '#888888'} 
            metalness={0.3}
            roughness={0.7}
          />
        </mesh>

        {colonyColor && (
          <mesh scale={0.22}>
            <sphereGeometry args={[1, 32, 32]} />
            <meshStandardMaterial 
              color={colonyColor} 
              transparent 
              opacity={0.2}
              roughness={1}
            />
          </mesh>
        )}
      </group>
    );
  } catch (error) {
    console.error('Error loading base model:', error);
    // Render a simple fallback if model fails to load
    return (
      <group dispose={null}>
        <mesh scale={0.1}>
          <boxGeometry args={[1, 0.5, 1]} />
          <meshStandardMaterial color={colonyColor || '#888888'} />
        </mesh>
      </group>
    );
  }
}

useGLTF.preload('/models/structures/Base_Small-transformed.glb');