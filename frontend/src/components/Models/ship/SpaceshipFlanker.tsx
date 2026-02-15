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

export function SpaceshipFlanker({ colonyColor, isAttacking, target }: ShipProps): React.JSX.Element {
  const { nodes: n, materials: m } = useGLTF('/models/fleet/Spaceship_Flanker.glb') as unknown as TrackGLTF

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
    let raf = 0;
    let last = performance.now();
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

        const geom = new THREE.BoxGeometry(0.01, 0.3, 0.01);
        const mat = new THREE.MeshBasicMaterial({ color: '#ff0040' });
        const mesh = new THREE.Mesh(geom, mat);
        
        const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);

        mesh.position.copy(origin);
        mesh.quaternion.copy(quaternion)
        // add to scene so mesh.position is world-space and velocity applies directly
        scene.add(mesh);

        const id = String(Math.random()).slice(2);
        const ttl = origin.distanceTo(targetPos) / speed + 1.0; // Buffer for safety
        projectilesRef.current.push({ id, mesh, velocity: dir.multiplyScalar(speed), ttl, targetPos });
      }

      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [isAttacking, target, scene]);

  return (
    <group ref={groupRef} dispose={null} scale={0.001}>
      <mesh geometry={n.Lo_poly_Spaceship_05_by_Liz_Reddington_1.geometry} material={m.lambert4SG} />
      <mesh geometry={n.Lo_poly_Spaceship_05_by_Liz_Reddington_1_1.geometry}>
        <meshStandardMaterial color={colonyColor} />
      </mesh>
      <mesh geometry={n.Lo_poly_Spaceship_05_by_Liz_Reddington_1_2.geometry} material={m.lambert2SG} />
    </group>
  )
}

useGLTF.preload('/models/fleet/Spaceship_Flanker.glb')



