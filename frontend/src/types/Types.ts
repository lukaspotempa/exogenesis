export interface Colony {
    name: string;
    residents: number;
    color: string;
    planet: Planet;
}

export interface Planet {
    position: { x: number, y: number, z: number}
    scale: number;
    rot: { x: number, y: number, z: number};
    planetModelName: string;
}