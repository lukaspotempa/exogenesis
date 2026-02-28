import { Canvas, useThree, useFrame } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import './styles.css'
import './assets/UI.css'
import { MainScene } from './components/Scene/MainScene'
import { GalaxySkybox } from './components/Scene/GalaxySkybox'
import ColonyList from './components/UI/ColonyList'
import PlanetDetails from './components/UI/PlanetDetails'
import ActionLog from './components/UI/ActionLog'
import VictoryScreen from './components/UI/VictoryScreen'
import { Suspense, useCallback, useEffect, useState, useRef } from 'react'
import * as THREE from 'three'
import { coloniesStore } from './store/coloniesStore'
import { sampleColonies } from './data/sampleData'
import type { Colony, Fleet, GameOverPayload } from './types/Types'

interface ControlsLike {
  target: THREE.Vector3;
  update: () => void;
  object?: THREE.Camera;
}

function CameraController({
  position = [0, 0, 50] as [number, number, number],
  lookAt = [0, 0, 0] as [number, number, number],
  controlsRef,
  isUserInitiated = false,
}: {
  position?: [number, number, number];
  lookAt?: [number, number, number];
  controlsRef?: React.RefObject<ControlsLike | null>;
  isUserInitiated?: boolean;
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
    // Skip camera updates if not user initiated
    if (!isUserInitiated) return;
    
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
  }, [posKey, lookKey, position, lookAt, camera, controlsRef, isUserInitiated]);

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
  const [isUserInitiatedChange, setIsUserInitiatedChange] = useState(true);
  const [actionEvents, setActionEvents] = useState(() => coloniesStore.getActionEvents());
  const [activeFleetId, setActiveFleetId] = useState<string | null>(null);
  const [camPosition, setCamPosition] = useState<[number, number, number]>([0, 0, 50]);
  const [camLookAt, setCamLookAt] = useState<[number, number, number]>([0, 0, 0]);
  const [gameOver, setGameOver] = useState<GameOverPayload | null>(null);
  const controlsRef = useRef<ControlsLike | null>(null);
  const handleControlsRef = (instance: unknown) => {

    if (instance && typeof instance === 'object') {
      controlsRef.current = instance as ControlsLike;
    }
  };
  const websocketConnection = useRef<WebSocket>(null);

  useEffect(() => {
    const unsubscribe = coloniesStore.subscribe(() => {
      const updatedColonies = coloniesStore.getColonies();
      setColonies(updatedColonies);
      
      // Update action events
      setActionEvents(coloniesStore.getActionEvents());
      
      if (activeColony) {
        const updatedActiveColony = updatedColonies.find(colony => colony.id === activeColony.id);
        if (updatedActiveColony) {
          setIsUserInitiatedChange(false);
          setActiveColony(updatedActiveColony);
        }
      }
    });
    
    return unsubscribe;
  }, [activeColony]);

  useEffect(() => {
    const URL = import.meta.env.VITE_WEBSOCKET_URL || "ws://localhost:8000/ws";
    console.log('WebSocket URL:', URL);
    if (!URL) return;
    const socket = new WebSocket(URL);

    socket.onmessage = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data);
        
        if (data && data.type === 'snapshot' && Array.isArray(data.colonies)) {
          // Initial snapshot (also sent after game restart)
          coloniesStore.setColonies(data.colonies);
          
          if (data.actionEvents && Array.isArray(data.actionEvents)) {
            coloniesStore.setActionEvents(data.actionEvents);
          } else {
            coloniesStore.clearActionEvents();
          }
          
          setColonies(data.colonies as Colony[]);
          const firstColony = (data.colonies as Colony[])?.[0] ?? null;
          setActiveColony(firstColony);
          if (firstColony) {
            setCamPosition([firstColony.planet.position.x, firstColony.planet.position.y, firstColony.planet.position.z + 30]);
            setCamLookAt([firstColony.planet.position.x, firstColony.planet.position.y, firstColony.planet.position.z]);
            setIsUserInitiatedChange(true);
          }
          setActiveFleetId(null);
          setGameOver(null);
          return;
        }
        
        if (data && data.type === 'update' && Array.isArray(data.changes)) {
          // Delta update; only update changed colonies
          coloniesStore.updateColonies(data.changes);
          return;
        }
        
        if (data && data.type === 'action' && data.event) {
          // Action event from backend
          coloniesStore.addActionEvent(data.event);
          return;
        }

        if (data && data.type === 'game_over') {
          setGameOver({
            winner: data.winner,
            actionHistory: data.actionHistory ?? [],
            restartAt: data.restartAt,
          });
          return;
        }
      } catch {
        // not JSON
      }
      onMessage(ev);
    };

    socket.addEventListener("open", () => {
      console.log('WebSocket connected');
      socket.send(JSON.stringify({ initialConnection: true }));
      const pingId = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' }));
      }, 10000);

      (socket as unknown as Record<string, unknown>)["__pingId"] = pingId;
    });

    socket.addEventListener("close", () => {
      console.log('WebSocket disconnected');
    });

    socket.addEventListener("error", (error) => {
      console.error('WebSocket error:', error);
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
    const first = sampleColonies?.[0] ?? null;
    setActiveColony(first);
    if (first) {
      setCamPosition([first.planet.position.x, first.planet.position.y, first.planet.position.z + 30]);
      setCamLookAt([first.planet.position.x, first.planet.position.y, first.planet.position.z]);
    }
    setIsUserInitiatedChange(true);
  }, []);

  useEffect(() => {
    if (!activeColony && colonies.length) setActiveColony(colonies[0]);
  }, [colonies, activeColony]);

  const handleSelectColony = useCallback((colony: Colony) => {
    setIsUserInitiatedChange(true);
    setActiveColony(colony);
    setActiveFleetId(null);
    setCamPosition([colony.planet.position.x, colony.planet.position.y, colony.planet.position.z + 30]);
    setCamLookAt([colony.planet.position.x, colony.planet.position.y, colony.planet.position.z]);
  }, []);

  const handleSelectFleet = useCallback((fleet: Fleet) => {
    setIsUserInitiatedChange(true);
    setActiveFleetId(fleet.id);
    setCamPosition([fleet.position.x, fleet.position.y, fleet.position.z + 15]);
    setCamLookAt([fleet.position.x, fleet.position.y, fleet.position.z]);
  }, []);

  const handleGameRestart = useCallback(() => {
    setGameOver(null);
  }, []);

  return (
    <div>
      <div style={{ width: '100vw', height: '100vh', background: 'black' }}>
        <div className="ui-wrapper">
          <div className="colony-list-container">
            <ColonyList 
              colonies={colonies} 
              activeColony={activeColony!} 
              setActiveColony={handleSelectColony}
              onSelectFleet={handleSelectFleet}
              activeFleetId={activeFleetId ?? undefined}
            />
          </div>
          <div className="colony-details-container">
            <PlanetDetails activeColony={activeColony!} setActiveColony={setActiveColony} />
          </div>
          <div className="action-log-container">
            <ActionLog events={actionEvents} />
          </div>
        </div>
        {gameOver && (
          <VictoryScreen gameOver={gameOver} onRestart={handleGameRestart} />
        )}
        <Canvas shadows>
          <Suspense fallback={null}>
            {/* compute camera target from active colony position */}
            <CameraController
              position={camPosition}
              lookAt={camLookAt}
              controlsRef={controlsRef}
              isUserInitiated={isUserInitiatedChange}
            />

            <MainScene />
            <GalaxySkybox />

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
