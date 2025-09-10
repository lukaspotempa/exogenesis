import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface BaseSmallGLTF extends GLTF {
    nodes: {
        "Cylinder001": Mesh,
        "Cylinder001_1": Mesh
    };
    materials: {
        mat22: MeshStandardMaterial,
        mat10: MeshStandardMaterial;
    };
}

interface Props {
    colonyColor?: string;
}

export function BaseFlag({ colonyColor }: Props): React.JSX.Element {
    const gltf = useGLTF('/models/structures/BaseFlag.glb') as unknown as Partial<BaseSmallGLTF>;
    const nodes = gltf.nodes as BaseSmallGLTF['nodes'] | undefined;
  const materials = gltf.materials as BaseSmallGLTF['materials'] | undefined;

  // If model data isn't available yet, render a simple fallback
  if (!nodes || !materials) {
    console.error('Base model nodes/materials not available, rendering fallback');
    return (
      <group dispose={null}>
        <mesh scale={0.5}>
          <boxGeometry args={[1, 0.5, 1]} />
          <meshStandardMaterial color={colonyColor || '#888888'} />
        </mesh>
      </group>
    );
  }

    if (!nodes || !materials) {
        console.error('Base model nodes/materials not available, rendering fallback');
        return (
            <group dispose={null}>
                <mesh 
                    scale={0.5}
                >
                    <boxGeometry args={[1, 2, 0.1]} />
                    <meshStandardMaterial color={colonyColor || '#ff0000'} />
                </mesh>
            </group>
        );
    }

    return (
        <group 
            dispose={null}
            scale={1}
        >
            {/* Center the model by offsetting it by its bounding box center */}
            <group>
                <mesh geometry={nodes['Cylinder001'].geometry} material={materials.mat22} />
                <mesh geometry={nodes['Cylinder001_1'].geometry}>
                    <meshStandardMaterial 
                    color={colonyColor || '#888888'} 
                    metalness={0.3}
                    roughness={0.7}
                    />
                </mesh>
            </group>
        </group>
    );
}