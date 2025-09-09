import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import './styles.css'
import { MainScene } from './components/Scene/MainScene'
import { Suspense, useEffect } from 'react'
import { coloniesStore } from './store/coloniesStore'
import { sampleColonies } from './data/sampleData'

function App() {
  useEffect(() => {
    // Initialize the store with sample data
    coloniesStore.setColonies(sampleColonies);
  }, []);

  return (
    <div style={{ width: '100vw', height: '100vh', background: 'black' }}>
      <Canvas shadows camera={{ position: [0, 0, 50], fov: 45 }}>
        <Suspense fallback={null}>
          <MainScene />

          {/* Controls */}
          <OrbitControls
            enablePan={true}
            enableZoom={true}
            enableRotate={true}
          />
        </Suspense>
      </Canvas>
    </div>
  )
}

export default App
