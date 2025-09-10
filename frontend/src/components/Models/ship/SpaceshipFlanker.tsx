import { useGLTF } from '@react-three/drei'
import type { GLTF } from 'three-stdlib'
import type { Mesh, MeshStandardMaterial } from 'three'

interface TrackGLTF extends GLTF {
  nodes: {
    'Lo_poly_Spaceship_05_by_Liz_Reddington_1': Mesh,
    'Lo_poly_Spaceship_05_by_Liz_Reddington_1_1': Mesh,
    'Lo_poly_Spaceship_05_by_Liz_Reddington_1_2': Mesh
  }
  materials: {
    'lambert2SG': MeshStandardMaterial,
    'lambert3SG': MeshStandardMaterial,
    'lambert4SG': MeshStandardMaterial
  }
}

export function SpaceshipFlanker(): React.JSX.Element {
  const { nodes: n, materials: m } = useGLTF('/models/fleet/Spaceship_Flanker.glb') as unknown as TrackGLTF

  return (
    <group dispose={null} scale={0.01}>
      <mesh geometry={n.Lo_poly_Spaceship_05_by_Liz_Reddington_1.geometry} material={m.lambert2SG} />
      <mesh geometry={n.Lo_poly_Spaceship_05_by_Liz_Reddington_1_1.geometry} material={m.lambert4SG} />
      <mesh geometry={n.Lo_poly_Spaceship_05_by_Liz_Reddington_1_2.geometry} material={m.lambert3SG} />
    </group>
  )
}

useGLTF.preload('/models/fleet/Spaceship_Flanker.glb')



