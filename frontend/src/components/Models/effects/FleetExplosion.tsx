import { useRef, useEffect, useState } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';

interface ExplosionProps {
  position: THREE.Vector3;
  onComplete: () => void;
}

export function FleetExplosion({ position, onComplete }: ExplosionProps) {
  const groupRef = useRef<THREE.Group>(null);
  const particlesRef = useRef<THREE.Points>(null);
  const geometryRef = useRef<THREE.BufferGeometry>(null);
  const [particles] = useState(() => {
    // Create particle geometry
    const particleCount = 50;
    const positions = new Float32Array(particleCount * 3);
    const velocities = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const lifetimes = new Float32Array(particleCount);
    
    for (let i = 0; i < particleCount; i++) {
      // Initial position (at explosion center)
      positions[i * 3] = 0;
      positions[i * 3 + 1] = 0;
      positions[i * 3 + 2] = 0;
      
      // Random velocity in all directions
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.random() * Math.PI;
      const speed = 2 + Math.random() * 3;
      
      velocities[i * 3] = Math.sin(phi) * Math.cos(theta) * speed;
      velocities[i * 3 + 1] = Math.sin(phi) * Math.sin(theta) * speed;
      velocities[i * 3 + 2] = Math.cos(phi) * speed;
      
      // Color variation (orange to yellow to white)
      const colorChoice = Math.random();
      if (colorChoice < 0.4) {
        // Orange
        colors[i * 3] = 1.0;
        colors[i * 3 + 1] = 0.4 + Math.random() * 0.2;
        colors[i * 3 + 2] = 0.0;
      } else if (colorChoice < 0.7) {
        // Yellow
        colors[i * 3] = 1.0;
        colors[i * 3 + 1] = 0.8 + Math.random() * 0.2;
        colors[i * 3 + 2] = 0.0;
      } else {
        // White-ish
        colors[i * 3] = 1.0;
        colors[i * 3 + 1] = 1.0;
        colors[i * 3 + 2] = 0.8 + Math.random() * 0.2;
      }
      
      // Random lifetime
      lifetimes[i] = 0.5 + Math.random() * 0.5;
    }
    
    return { positions, velocities, colors, lifetimes, particleCount };
  });
  
  const ageRef = useRef(0);
  const maxLifetime = 1.5; // Maximum explosion duration
  
  useFrame((_state, delta) => {
    if (!particlesRef.current) return;
    
    ageRef.current += delta;
    
    // Update particle positions
    const positions = particlesRef.current.geometry.attributes.position.array as Float32Array;
    const colors = particlesRef.current.geometry.attributes.color.array as Float32Array;
    
    let anyAlive = false;
    
    for (let i = 0; i < particles.particleCount; i++) {
      const lifetime = particles.lifetimes[i];
      const age = ageRef.current;
      
      if (age < lifetime) {
        anyAlive = true;
        
        // Update position based on velocity
        positions[i * 3] += particles.velocities[i * 3] * delta;
        positions[i * 3 + 1] += particles.velocities[i * 3 + 1] * delta;
        positions[i * 3 + 2] += particles.velocities[i * 3 + 2] * delta;
        
        // Fade out based on age
        const lifeRatio = age / lifetime;
        const alpha = 1.0 - lifeRatio;
        
        // Dim the colors as they age
        const baseColor = particles.colors.slice(i * 3, i * 3 + 3);
        colors[i * 3] = baseColor[0] * alpha;
        colors[i * 3 + 1] = baseColor[1] * alpha;
        colors[i * 3 + 2] = baseColor[2] * alpha;
      } else {
        // Dead particle - make invisible
        colors[i * 3] = 0;
        colors[i * 3 + 1] = 0;
        colors[i * 3 + 2] = 0;
      }
    }
    
    particlesRef.current.geometry.attributes.position.needsUpdate = true;
    particlesRef.current.geometry.attributes.color.needsUpdate = true;
    
    // Clean up when all particles are dead
    if (!anyAlive || ageRef.current > maxLifetime) {
      onComplete();
    }
  });
  
  useEffect(() => {
    if (groupRef.current) {
      groupRef.current.position.copy(position);
    }
    
    // Set up the geometry with attributes
    if (geometryRef.current) {
      geometryRef.current.setAttribute(
        'position',
        new THREE.BufferAttribute(particles.positions, 3)
      );
      geometryRef.current.setAttribute(
        'color',
        new THREE.BufferAttribute(particles.colors, 3)
      );
    }
  }, [position, particles.positions, particles.colors]);
  
  return (
    <group ref={groupRef}>
      <points ref={particlesRef}>
        <bufferGeometry ref={geometryRef} />
        <pointsMaterial
          size={0.15}
          vertexColors
          transparent
          opacity={1.0}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  );
}
