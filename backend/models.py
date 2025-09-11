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
    oil: float
    steel: float
    water: float
    temperature: float


class ResourceStation(BaseModel):
    position: Vector2
    resourceType: Literal["oil", "steel", "water", "temperature"]


class Planet(BaseModel):
    position: Vector3
    scale: float
    rot: Vector3
    planetModelName: str
    planetMainBase: Vector2
    planetNaturalResources: NaturalResources
    planetResourceStation: Optional[List[ResourceStation]] = None


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


class Colony:
    """Wrapper class for colony management
    """

    def __init__(self, colony: ColonyModel):
        self.colony = colony

    def to_dict(self):
        return self.colony.dict()

    def add_fleet(self, fleet: Fleet):
        if self.colony.colonyFleet is None:
            self.colony.colonyFleet = []
        self.colony.colonyFleet.append(fleet)

    def remove_fleet(self, fleet_id: str):
        if not self.colony.colonyFleet:
            return
        self.colony.colonyFleet = [f for f in self.colony.colonyFleet if f.id != fleet_id]

    def change_residents(self, delta: int):
        self.colony.residents = max(0, self.colony.residents + delta)


