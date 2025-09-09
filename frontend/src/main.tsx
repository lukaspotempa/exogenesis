import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { useGLTF } from '@react-three/drei'

// Preload GLTF models
useGLTF.preload('/models/earth/Earth.glb')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
