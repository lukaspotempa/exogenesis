import { useGLTF } from '@react-three/drei'
import type { GLTF } from 'three-stdlib'
import type { MeshStandardMaterial, Mesh } from 'three'

import { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { useThree } from '@react-three/fiber';

interface ShipProps {
  colonyColor: string;
  isAttacking?: boolean;
  target?: { id?: string; position?: { x: number; y: number; z?: number } };
}

// Nodes names from Spaceship_Scout.jsx
// Lo_poly_Spaceship_04_by_Liz_Reddington_1
// Lo_poly_Spaceship_04_by_Liz_Reddington_1_1
// Lo_poly_Spaceship_04_by_Liz_Reddington_1_2

// Materials from Spaceship_Scout.jsx
// lambert4SG
// lambert3SG
// lambert2SG

interface TrackGLTF extends GLTF {
  nodes: {
    'Lo_poly_Spaceship_04_by_Liz_Reddington_1': Mesh,
    'Lo_poly_Spaceship_04_by_Liz_Reddington_1_1': Mesh,
    'Lo_poly_Spaceship_04_by_Liz_Reddington_1_2': Mesh
  }
  materials: {
    'lambert2SG': MeshStandardMaterial,
    'lambert3SG': MeshStandardMaterial,
    'lambert4SG': MeshStandardMaterial
  }
}

export function SpaceshipScout({ colonyColor, isAttacking, target }: ShipProps): React.JSX.Element {
  const { nodes: n, materials: m } = useGLTF('/models/fleet/Spaceship_Scout-transformed.glb') as unknown as TrackGLTF

  const groupRef = useRef<THREE.Group | null>(null);
  const projectilesRef = useRef<Array<{ id: string; mesh: THREE.Mesh; velocity: THREE.Vector3; ttl: number; targetPos: THREE.Vector3 }>>([]);
  const fireCooldownRef = useRef<number>(0);
  const { scene } = useThree();

   // Animate projectiles and spawn when attacking
   useEffect(() => {
    return () => {
      projectilesRef.current.forEach(p => {
        if (p.mesh.parent) p.mesh.parent.remove(p.mesh);
        p.mesh.geometry.dispose();
        // @ts-expect-error: material type union prevents precise typing
        p.mesh.material.dispose();
      });
      projectilesRef.current.length = 0;
    };
  }, []);

  // per-frame projectile update using requestAnimationFrame through three's frame loop is preferable,
  // but to keep this component self-contained we use a small internal RAF loop here.
  useEffect(() => {
    let last = performance.now();
    let frameId: number;
    const loop = (t: number) => {
      const delta = (t - last) / 1000;
      last = t;

      // update existing projectiles (world-space)
      if (projectilesRef.current.length > 0) {
        const remaining: typeof projectilesRef.current = [];
        projectilesRef.current.forEach(p => {
          p.ttl -= delta;
          const prevPos = p.mesh.position.clone();
          p.mesh.position.addScaledVector(p.velocity, delta); // mesh in scene (world coords)
          
          // Check if projectile has reached or passed the target
          const distToTarget = p.mesh.position.distanceTo(p.targetPos);
          const prevDistToTarget = prevPos.distanceTo(p.targetPos);
          
          // If we're now farther from target than before, or very close, we've hit/passed it
          if (distToTarget > prevDistToTarget || distToTarget < 0.5) {
            // Hit! Remove projectile
            if (p.mesh.parent) p.mesh.parent.remove(p.mesh);
          } else if (p.ttl > 0) {
            remaining.push(p);
          } else {
            if (p.mesh.parent) p.mesh.parent.remove(p.mesh);
          }
        });
        if (remaining.length !== projectilesRef.current.length) projectilesRef.current = remaining;
      }

      // handle firing
      fireCooldownRef.current -= delta;
      if (isAttacking && target?.position && fireCooldownRef.current <= 0 && groupRef.current) {
        fireCooldownRef.current = 1 + Math.random();
        const origin = new THREE.Vector3();
        groupRef.current.getWorldPosition(origin);
        const targetPos = new THREE.Vector3(target.position.x, target.position.y, target.position.z ?? 0);
        const dir = targetPos.clone().sub(origin).normalize();
        const speed = 5;
        const bulletSpeed = speed * 1.5; // Scout fires fast projectiles
        // Use distance-based TTL so bullets always reach the target regardless of
        // how far the fleet has parked from the base (parking distance varies 14–20 units).
        const ttl = origin.distanceTo(targetPos) / bulletSpeed + 1.0;

        // Scout has fast, small projectiles
        const geom = new THREE.BoxGeometry(0.005, 0.4, 0.005);
        const mat = new THREE.MeshBasicMaterial({ color: '#55ff55' });
        const mesh = new THREE.Mesh(geom, mat);
        
        const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);

        mesh.position.copy(origin);
        mesh.quaternion.copy(quaternion);
        
        scene.add(mesh);
        
        projectilesRef.current.push({
          id: Math.random().toString(),
          mesh,
          velocity: dir.multiplyScalar(bulletSpeed),
          ttl,
          targetPos
        });
      }
      
      frameId = requestAnimationFrame(loop);
    };
    frameId = requestAnimationFrame(loop);
    
    return () => cancelAnimationFrame(frameId);
  }, [isAttacking, target, scene]);

  return (
    <group ref={groupRef} dispose={null} scale={0.001}>
      <mesh geometry={n['Lo_poly_Spaceship_04_by_Liz_Reddington_1'].geometry} material={m.lambert4SG} />
      <mesh geometry={n['Lo_poly_Spaceship_04_by_Liz_Reddington_1_1'].geometry}>
        <meshStandardMaterial color={colonyColor} />
      </mesh>
      <mesh geometry={n['Lo_poly_Spaceship_04_by_Liz_Reddington_1_2'].geometry} material={m.lambert2SG} />
    </group>
  )
}

useGLTF.preload('/models/fleet/Spaceship_Scout-transformed.glb')
