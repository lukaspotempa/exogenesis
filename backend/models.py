from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from enum import Enum


class Vector2(BaseModel):
    x: float
    y: float


class Vector3(BaseModel):
    x: float
    y: float
    z: float


class NaturalResources(BaseModel):
    # Generation rates (per tick)
    oil: float
    steel: float
    water: float
    temperature: float  # Environmental factor (not stored, affects growth)
    
    # Storage (accumulated resources)
    oilStorage: float = 0.0
    steelStorage: float = 0.0
    waterStorage: float = 0.0


class ResourceStation(BaseModel):
    position: Vector2
    resourceType: Literal["oil", "steel", "water", "temperature"]


class OilPump(BaseModel):
    id: str
    position: Vector2
    production: float = 0.0  # Oil produced per tick (0-2)


class Planet(BaseModel):
    position: Vector3
    scale: float
    rot: Vector3
    planetModelName: str
    planetMainBase: Vector2
    planetNaturalResources: NaturalResources
    planetResourceStation: Optional[List[ResourceStation]] = None
    oilPumps: Optional[List[OilPump]] = None


class ColonyLevel(str, Enum):
    Colony = 'Colony'
    Settlement = 'Settlement'
    Township = 'Township'
    Metropolis = 'Metropolis'
    StarportHub = 'Starport Hub'


class FleetOrder(BaseModel):
    type: Literal["Move", "Attack", "Patrol", "Hold", "Retreat", "Dock"]
    targetId: Optional[str] = None
    targetPos: Optional[Vector3] = None
    timestamp: Optional[int] = None


class FleetTarget(BaseModel):
    id: Optional[str] = None
    position: Optional[Vector3] = None


class Fleet(BaseModel):
    id: str
    type: Literal["Attacker", "Flanker", "Fighter", "Bomber"]
    label: Optional[str] = None
    count: Optional[int] = 1
    position: Vector3
    velocity: Vector3
    state: Literal["Idle", "Moving", "Attacking", "Retreating", "Patrolling", "Docking"]
    tactic: Literal["Offensive", "Defensive", "Skirmish", "Kite", "Hold"]
    order: Optional[FleetOrder] = None
    leaderId: Optional[str] = None
    hpPool: Optional[float] = None
    target: Optional[FleetTarget] = None
    isAttacking: Optional[bool] = False


class ColonyModel(BaseModel):
    id: str
    name: str
    residents: int
    color: str
    planet: Planet
    colonyLevel: ColonyLevel
    colonyFleet: Optional[List[Fleet]] = None



