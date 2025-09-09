import React from 'react';
import type { Planet as PlanetType } from '../../types/Types';
import { PlanetA } from './planets/PlanetA';

interface PlanetProps {
  planet: PlanetType;
  colonyColor?: string;
}

export function Planet({ planet, colonyColor }: PlanetProps): React.JSX.Element {
  const { position, scale, rot, planetModelName } = planet;

  const renderPlanetModel = () => {
    switch (planetModelName) {
      case 'Planet_A':
        return <PlanetA colonyColor={colonyColor} />;
      default:
        console.warn(`Unknown planet model: ${planetModelName}`);
        return <PlanetA colonyColor={colonyColor} />;
    }
  };

  return (
    <group 
      position={[position.x, position.y, position.z]}
      scale={scale}
      rotation={[rot.x, rot.y, rot.z]}
    >
      {renderPlanetModel()}
    </group>
  );
}