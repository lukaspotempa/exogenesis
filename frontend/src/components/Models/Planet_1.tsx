import { useGLTF } from '@react-three/drei'
import type { GLTF } from 'three-stdlib'
import type { Mesh, MeshStandardMaterial } from 'three'

interface TrackGLTF extends GLTF {
  nodes: {
    Jupiter_Sphere: Mesh,
  }
  materials: {
    'Material.005': MeshStandardMaterial
  }
}

export function Planet1(): React.JSX.Element {
  const { nodes: n, materials: m } = useGLTF('/models/earth/Jupiter-transformed.glb') as unknown as TrackGLTF
  const config = { receiveShadow: true, castShadow: true, 'material-roughness': 1 }


  return (
    <group dispose={null}>
      <mesh geometry={n.Jupiter_Sphere.geometry} material={m['Material.005']} />
    </group>
  )
}

useGLTF.preload('/models/earth/Jupiter-transformed.glb')



