export interface Colony {
    name: string;
    residents: number;
    color: string;
    planet: Planet;
}

export interface Planet {
    position: { x: number, y: number, z: number }
    scale: number;
    rot: { x: number, y: number, z: number };
    planetModelName: string;
    planetMainBase: { x: number, y: number }; // Main base location on a planet
    planetNaturalResources: NaturalResources;
    planetResourceStation?: ResourceStation[];
}

export interface NaturalResources {
    oil: number;
    steel: number;
    water: number;
    temperature: number;
}

export interface ResourceStation { // Resource Outposts like drilling stations, only available on planets
    position: { x: number, y: number }
    resourceType: keyof NaturalResources;
}