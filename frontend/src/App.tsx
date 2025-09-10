import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import './styles.css'
import './assets/UI.css'
import { MainScene } from './components/Scene/MainScene'
import ColonyList from './components/ColonyList'
import PlanetDetails from './components/PlanetDetails'
import { Suspense, useEffect, useState } from 'react'
import { coloniesStore } from './store/coloniesStore'
import { sampleColonies } from './data/sampleData'
import type { Colony } from './types/Types'

function App() {
  const [colonies, setColonies] = useState(() => coloniesStore.getColonies() ?? []);
  const [activeColony, setActiveColony] = useState<Colony | null>(null);

  useEffect(() => {
    // initialize store and local state
    coloniesStore.setColonies(sampleColonies);
    setColonies(sampleColonies);
    // set a sensible default active colony
    setActiveColony(sampleColonies?.[0] ?? null);
  }, []);

  // keep active when colonies are populated later
  useEffect(() => {
    if (!activeColony && colonies.length) setActiveColony(colonies[0]);
  }, [colonies, activeColony]);

  return (
    <div>
      <div style={{ width: '100vw', height: '100vh', background: 'black' }}>
        <div className="ui-wrapper">
          <div className="colony-list-container">
            <ColonyList colonies={colonies} activeColony={activeColony!} setActiveColony={setActiveColony} />
          </div>
          <div className="colony-details-container">
            <PlanetDetails activeColony={activeColony!} setActiveColony={setActiveColony} />
          </div>
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
