import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface PlanetBGLTF extends GLTF {
  nodes: {
    "Planet_6": Mesh;
  };
  materials: {
    'Atlas': MeshStandardMaterial;
  };
}

interface PlanetBProps {
  colonyColor?: string;
}

export function PlanetB({ colonyColor }: PlanetBProps): React.JSX.Element {
  const { nodes, materials } = useGLTF('/models/earth/PlanetB-transformed.glb') as unknown as PlanetBGLTF;

  console.log(nodes);
  if (!nodes || !materials) {
     console.log("Fallback rendered")
    // Fallback to a simple sphere if GLTF isn't available yet
    return (
      <group dispose={null}>
        <mesh name="planet-surface">
          <sphereGeometry args={[1, 32, 32]} />
          <meshStandardMaterial color="#4a4a4a" />
        </mesh>
        {colonyColor && (
          <mesh 
            scale={1.01} 
            name="colony-overlay"
            raycast={() => null} // Disable raycasting for this mesh
          >
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

  return (
    <group dispose={null}>
      <mesh 
        geometry={nodes["Planet_6"].geometry} 
        material={materials['Atlas']}
        receiveShadow
        castShadow
        name="planet-surface"
      />
    </group>
  );
}

useGLTF.preload('/models/earth/PlanetB-transformed.glb');