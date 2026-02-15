import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { useThree } from '@react-three/fiber';

interface BaseDefenseSystemProps {
  isAttacking?: boolean;
  targetPos?: { x: number; y: number; z: number };
}

export function BaseDefenseSystem({ isAttacking, targetPos }: BaseDefenseSystemProps): React.JSX.Element {
  const groupRef = useRef<THREE.Group | null>(null);
  const projectilesRef = useRef<Array<{ id: string; mesh: THREE.Mesh; velocity: THREE.Vector3; ttl: number; targetPos: THREE.Vector3 }>>([]);
  const fireCooldownRef = useRef<number>(0);
  const { scene } = useThree();

  // Cleanup projectiles on unmount
  useEffect(() => {
    return () => {
      projectilesRef.current.forEach(p => {
        if (p.mesh.parent) p.mesh.parent.remove(p.mesh);
        p.mesh.geometry.dispose();
        // @ts-expect-error: disposing material
        if (p.mesh.material.dispose) p.mesh.material.dispose();
      });
      projectilesRef.current.length = 0;
    };
  }, []);

  // Animation loop
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const loop = (t: number) => {
      const delta = (t - last) / 1000;
      last = t;

      // Update existing projectiles
      if (projectilesRef.current.length > 0) {
        const remaining: typeof projectilesRef.current = [];
        projectilesRef.current.forEach(p => {
          p.ttl -= delta;
          const prevPos = p.mesh.position.clone();
          p.mesh.position.addScaledVector(p.velocity, delta);
          
          // Check if projectile has reached or passed the target
          const distToTarget = p.mesh.position.distanceTo(p.targetPos);
          const prevDistToTarget = prevPos.distanceTo(p.targetPos);
          
          // If we're now farther from target than before, or very close, we've hit/passed it
          if (distToTarget > prevDistToTarget || distToTarget < 0.8) {
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

      // Handle firing
      fireCooldownRef.current -= delta;
      
      if (isAttacking && targetPos && fireCooldownRef.current <= 0 && groupRef.current) {
        // Fire rate for base
        fireCooldownRef.current = 0.5 + Math.random() * 0.5; 
        
        const origin = new THREE.Vector3();
        groupRef.current.getWorldPosition(origin);
        // Elevate origin slightly (base height) - world space up?
        // simple y add might not be "up" on a sphere.
        // But the group is rotated. Local Y is up.
        // So we can offset locally before getting world position?
        // Or just spawn it at the group origin (base center) for now.
        
        const tPos = new THREE.Vector3(targetPos.x, targetPos.y, targetPos.z);
        const dir = tPos.clone().sub(origin).normalize();
        const speed = 15; // Fast lasers

        // Projectile visual
        const geom = new THREE.BoxGeometry(0.05, 0.4, 0.05);
        const mat = new THREE.MeshBasicMaterial({ color: '#ff5500' });
        const mesh = new THREE.Mesh(geom, mat);
        
        const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);

        mesh.position.copy(origin);
        mesh.quaternion.copy(quaternion);
        
        scene.add(mesh); // Add to world scene

        const id = String(Math.random()).slice(2);
        const ttl = origin.distanceTo(tPos) / speed + 0.5; // Small buffer for safety
        projectilesRef.current.push({ id, mesh, velocity: dir.multiplyScalar(speed), ttl, targetPos: tPos });
      }

      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [isAttacking, targetPos, scene]);

  return <group ref={groupRef} position={[0, 1.5, 0]} />; // Offset local Y (Up)
}
