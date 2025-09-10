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
  try {
    const { nodes, materials } = useGLTF('/models/earth/Jupiter-transformed.glb') as unknown as PlanetAGLTF;

    return (
      <group dispose={null}>
        <mesh 
          geometry={nodes.Jupiter_Sphere.geometry} 
          material={materials['Material.005']}
          receiveShadow
          castShadow
          name="planet-surface"
        />

      </group>
    );
  } catch (error) {
    console.error('Error loading planet model:', error);
    // Fallback to a simple sphere if GLTF fails
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
}

useGLTF.preload('/models/earth/Jupiter-transformed.glb');