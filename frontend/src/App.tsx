import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import './styles.css'
import './assets/UI.css'
import { MainScene } from './components/Scene/MainScene'
import ColonyList from './components/ColonyList'
import { Suspense, useEffect, useState } from 'react'
import { coloniesStore } from './store/coloniesStore'
import { sampleColonies } from './data/sampleData'

function App() {
  const [colonies, setColonies] = useState(() => coloniesStore.getColonies() ?? []);
  const [activeColony, setActiveColony] = useState<string | null>(null);

  useEffect(() => {
    // initialize store and local state
    coloniesStore.setColonies(sampleColonies);
    setColonies(sampleColonies);
    // set a sensible default active colony
    setActiveColony(sampleColonies?.[0]?.name ?? null);
  }, []);

  // keep active when colonies are populated later
  useEffect(() => {
    if (!activeColony && colonies.length) setActiveColony(colonies[0].name);
  }, [colonies, activeColony]);

  return (
    <div>
      <div style={{ width: '100vw', height: '100vh', background: 'black' }}>
        <div className="UI">
          <ColonyList colonies={colonies} activeColony={activeColony} setActiveColony={setActiveColony} />
        </div>
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
    </div>
  )
}

export default App
