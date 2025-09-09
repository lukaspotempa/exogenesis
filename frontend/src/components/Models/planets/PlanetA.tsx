import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface PlanetAGLTF extends GLTF {
  nodes: {
    Jupiter_Sphere: Mesh;
  };
  materials: {
    'Material.005': MeshStandardMaterial;
  };
}

interface PlanetAProps {
  colonyColor?: string;
}

export function PlanetA({ colonyColor }: PlanetAProps): React.JSX.Element {
  const { nodes, materials } = useGLTF('/models/earth/Jupiter-transformed.glb') as unknown as PlanetAGLTF;

  return (
    <group dispose={null}>
      <mesh 
        geometry={nodes.Jupiter_Sphere.geometry} 
        material={materials['Material.005']}
        receiveShadow
        castShadow
      />
      {colonyColor && (
        <mesh scale={1.01}>
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
}

useGLTF.preload('/models/earth/Jupiter-transformed.glb');