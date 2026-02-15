import { Stars } from '@react-three/drei';

export function GalaxySkybox() {
  return (
    <>
      <color attach="background" args={['#000005']} /> {/* Deep space black */}
      <Stars 
        radius={300} 
        depth={60} 
        count={20000} 
        factor={7} 
        saturation={0} 
        fade 
        speed={1} 
      />
    </>
  );
}
