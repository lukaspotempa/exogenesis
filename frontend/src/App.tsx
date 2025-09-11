import { Canvas, useThree, useFrame } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import './styles.css'
import './assets/UI.css'
import { MainScene } from './components/Scene/MainScene'
import ColonyList from './components/UI/ColonyList'
import PlanetDetails from './components/UI/PlanetDetails'
import { Suspense, useEffect, useState, useRef } from 'react'
import * as THREE from 'three'
import { coloniesStore } from './store/coloniesStore'
import { sampleColonies } from './data/sampleData'
import type { Colony } from './types/Types'

interface ControlsLike {
  target: THREE.Vector3;
  update: () => void;
}

function CameraController({
  position = [0, 0, 50] as [number, number, number],
  lookAt = [0, 0, 0] as [number, number, number],
  controlsRef,
}: {
  position?: [number, number, number];
  lookAt?: [number, number, number];
  controlsRef?: React.RefObject<ControlsLike | null>;
}) {
  const { camera } = useThree();

  const animRef = useRef({
    running: false,
    startTime: 0,
    duration: 1000,
    startPos: new THREE.Vector3(),
    targetPos: new THREE.Vector3(),
    startLookAt: new THREE.Vector3(),
    targetLookAt: new THREE.Vector3(),
  });

  // easing fn
  const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  const posKey = position.join(',');
  const lookKey = lookAt.join(',');


  useEffect(() => {
    const now = performance.now();
    const startPos = camera.position.clone();

    let startLookAt = new THREE.Vector3();
    const ctrl = controlsRef?.current ?? null;
    if (ctrl && ctrl.target) {
      startLookAt = ctrl.target.clone();
    } else {
      const dir = new THREE.Vector3();
      camera.getWorldDirection(dir);
      startLookAt = camera.position.clone().add(dir.multiplyScalar(10));
    }

    animRef.current.startPos.copy(startPos);
    animRef.current.targetPos.set(position[0], position[1], position[2]);
    animRef.current.startLookAt.copy(startLookAt);
    animRef.current.targetLookAt.set(lookAt[0], lookAt[1], lookAt[2]);
    animRef.current.startTime = now;
    animRef.current.running = true;
  }, [posKey, lookKey, position, lookAt, camera, controlsRef]);

  useFrame(() => {
    if (!animRef.current.running) return;
    const now = performance.now();
    const elapsed = now - animRef.current.startTime;
    const tRaw = Math.min(1, elapsed / animRef.current.duration);
    const t = easeInOutCubic(tRaw);

    // lerp
    camera.position.lerpVectors(animRef.current.startPos, animRef.current.targetPos, t);

    const lookAtPoint = new THREE.Vector3().lerpVectors(animRef.current.startLookAt, animRef.current.targetLookAt, t);
    camera.lookAt(lookAtPoint);

    const ctrl = controlsRef?.current ?? null;
    if (ctrl && ctrl.target) {
      ctrl.target.copy(lookAtPoint);
      if (typeof ctrl.update === 'function') ctrl.update();
    }

    if (tRaw >= 1) {
      camera.position.copy(animRef.current.targetPos);
      camera.lookAt(animRef.current.targetLookAt);
      const ctrl = controlsRef?.current ?? null;
      if (ctrl && ctrl.target) {
        ctrl.target.copy(animRef.current.targetLookAt);
        if (typeof ctrl.update === 'function') ctrl.update();
      }
      animRef.current.running = false;
    }
  });

  return null;
}

function onMessage(ev: MessageEvent) {
  console.log(ev);
}

function App() {
  const [colonies, setColonies] = useState(() => coloniesStore.getColonies() ?? []);
  const [activeColony, setActiveColony] = useState<Colony | null>(null);
  const controlsRef = useRef<ControlsLike | null>(null);
  const handleControlsRef = (instance: unknown) => {

    if (instance && typeof instance === 'object') {
      controlsRef.current = instance as ControlsLike;
    }
  };
  const websocketConnection = useRef<WebSocket>(null);

  useEffect(() => {
    const URL = import.meta.env.VITE_WEBSOCKET_URL;
    if (!URL) return;
    const socket = new WebSocket("ws://" + URL);

    socket.onmessage = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        if (data && data.type === 'snapshot' && Array.isArray(data.colonies)) {
          // update the global store and local state with snapshot
          coloniesStore.setColonies(data.colonies);
          setColonies(data.colonies as Colony[]);
          setActiveColony((data.colonies as Colony[])?.[0] ?? null);
          return;
        }
      } catch {
        // not JSON, fall through
      }
      onMessage(ev);
    };

    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({ initialConnection: true }));
      const pingId = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' }));
      }, 10000);

      (socket as unknown as Record<string, unknown>)["__pingId"] = pingId;
    });

    websocketConnection.current = socket;

  return () => {
      try {
        const pingId = (socket as unknown as Record<string, unknown>)["__pingId"] as number | undefined;
        if (pingId) clearInterval(pingId);
      } catch (e) {
        console.error(e)
      }
      websocketConnection.current?.close();
    };
  }, [])

  useEffect(() => {
    coloniesStore.setColonies(sampleColonies);
    setColonies(sampleColonies);
    setActiveColony(sampleColonies?.[0] ?? null);
  }, []);

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
        <Canvas shadows>
          <Suspense fallback={null}>
            {/* compute camera target from active colony position */}
            <CameraController
              position={activeColony ? [activeColony.planet.position.x, activeColony.planet.position.y, activeColony.planet.position.z + 30] : [0, 0, 50]}
              lookAt={activeColony ? [activeColony.planet.position.x, activeColony.planet.position.y, activeColony.planet.position.z] : [0, 0, 0]}
              controlsRef={controlsRef}
            />

            <MainScene />

            {/* Controls */}
            <OrbitControls
              ref={handleControlsRef}
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
