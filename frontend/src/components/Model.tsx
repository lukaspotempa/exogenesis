/*import { useLoader } from '@react-three/fiber'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader'
import { MTLLoader } from 'three/examples/jsm/loaders/MTLLoader'
import { Suspense } from 'react'

interface ModelProps {
  objPath: string
  mtlPath?: string
  position?: [number, number, number]
  scale?: [number, number, number]
  rotation?: [number, number, number]
}

function Model({
  objPath,
  mtlPath,
  position = [0, 0, 0],
  scale = [1, 1, 1],
  rotation = [0, 0, 0]
}: ModelProps) {
  const obj = useLoader(OBJLoader, objPath)

  if (mtlPath) {
    const materials = useLoader(MTLLoader, mtlPath)
    materials.preload()
    obj.traverse((child: any) => {
      if (child.isMesh) {
        child.material = materials.materials[child.material.name]
      }
    })
  }

  return (
    <primitive
      object={obj}
      position={position}
      scale={scale}
      rotation={rotation}
    />
  )
}

export function Scene({ objPath, mtlPath, position, scale, rotation }: ModelProps) {
  return (
    <Suspense fallback={null}>
      <Model
        objPath={objPath}
        mtlPath={mtlPath}
        position={position}
        scale={scale}
        rotation={rotation}
      />
    </Suspense>
  )
}*/