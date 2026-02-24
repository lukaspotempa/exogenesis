import React from 'react';
import { useGLTF } from '@react-three/drei';
import type { GLTF } from 'three-stdlib';
import type { Mesh, MeshStandardMaterial } from 'three';

interface MetropolisGLTF extends GLTF {
  nodes: {
    "group1172654828": Mesh;
    "Spaceship_BarbaraTheBee": Mesh;
    "landingpad_small": Mesh;
    "Highrise_12-Mesh002": Mesh;
    "Highrise_12-Mesh002_1": Mesh;
    "Highrise_12-Mesh002_2": Mesh;
    "Highrise_12-Mesh003": Mesh;
    "Highrise_12-Mesh003_1": Mesh;
  };
  materials: {
    PaletteMaterial005: MeshStandardMaterial;
    Atlas: MeshStandardMaterial;
    "spacebits_texture.001": MeshStandardMaterial;
    PaletteMaterial001: MeshStandardMaterial;
    PaletteMaterial002: MeshStandardMaterial;
    PaletteMaterial003: MeshStandardMaterial;
    PaletteMaterial004: MeshStandardMaterial;
    Texture_Signs: MeshStandardMaterial;
  };
}

const ColonyMetropolis = ({ colonyColor }: { colonyColor?: string }): React.JSX.Element => {
  // call hook unconditionally to satisfy React Hook rules
  const gltf = useGLTF('/models/structures/Metropolis-transformed.glb') as unknown as Partial<MetropolisGLTF>;
  const nodes = gltf.nodes as MetropolisGLTF['nodes'] | undefined;
  const materials = gltf.materials as MetropolisGLTF['materials'] | undefined;

  // If model data isn't available yet, render a simple fallback
  if (!nodes?.['Highrise_12-Mesh002'] || !materials?.PaletteMaterial001) {
    console.error('Metropolis model nodes/materials not available, rendering fallback');
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
    <group dispose={null} scale={0.05}>
      {nodes['group1172654828'] && materials.PaletteMaterial005 && (
        <mesh
          geometry={nodes['group1172654828'].geometry}
          material={materials.PaletteMaterial005}
          position={[0, 113.235, 15.96]}
          receiveShadow
          castShadow
        />
      )}
      {nodes['Spaceship_BarbaraTheBee'] && materials.Atlas && (
        <mesh
          geometry={nodes['Spaceship_BarbaraTheBee'].geometry}
          material={materials.Atlas}
          receiveShadow
          castShadow
        />
      )}
      {nodes['landingpad_small'] && materials['spacebits_texture.001'] && (
        <mesh
          geometry={nodes['landingpad_small'].geometry}
          material={materials['spacebits_texture.001']}
          position={[9.242, 4.749, 0]}
          scale={625.027}
          receiveShadow
          castShadow
        />
      )}
      <mesh
        geometry={nodes['Highrise_12-Mesh002'].geometry}
        material={materials.PaletteMaterial001}
        receiveShadow
        castShadow
      />
      {nodes['Highrise_12-Mesh002_1'] && materials.PaletteMaterial002 && (
        <mesh
          geometry={nodes['Highrise_12-Mesh002_1'].geometry}
          material={materials.PaletteMaterial002}
          receiveShadow
          castShadow
        />
      )}
      {nodes['Highrise_12-Mesh002_2'] && materials.PaletteMaterial003 && (
        <mesh
          geometry={nodes['Highrise_12-Mesh002_2'].geometry}
          material={materials.PaletteMaterial003}
          receiveShadow
          castShadow
        />
      )}
      {nodes['Highrise_12-Mesh003'] && materials.PaletteMaterial004 && (
        <mesh
          geometry={nodes['Highrise_12-Mesh003'].geometry}
          material={materials.PaletteMaterial004}
          receiveShadow
          castShadow
        />
      )}
      {nodes['Highrise_12-Mesh003_1'] && materials.Texture_Signs && (
        <mesh
          geometry={nodes['Highrise_12-Mesh003_1'].geometry}
          material={materials.Texture_Signs}
          receiveShadow
          castShadow
        />
      )}
    </group>
  );
};

useGLTF.preload('/models/structures/Metropolis-transformed.glb');

ColonyMetropolis.displayName = 'ColonyMetropolis';
export { ColonyMetropolis };