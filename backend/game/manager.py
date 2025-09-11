from typing import List
from fastapi import HTTPException
import uuid
import random
import math
import numpy as np
from ..models import ColonyModel, Planet
from .colony import Colony


class GameManager:
    """Manages colonies in-memory."""

    def __init__(self):
        self.colonies: List[Colony] = []

    def initialise_game(self, count: int = 3) -> List[dict]:
        created = []
        for i in range(count):
            payload = {
                "name": f"Colony {len(self.colonies) + 1}",
                "residents": int(random.uniform(10, 500)),
                "color": f"#{random.randint(0, 0xFFFFFF):06x}",
                "colonyLevel": "Colony",
            }
            created.append(self.create_colony(payload))
        return created
    
    def clear_colonies(self):
        self.colonies.clear()

    def list_colonies(self) -> List[dict]:
        return [c.to_dict() for c in self.colonies]

    def create_colony(self, payload: dict) -> dict:
        try:
            entity = Colony.create_colony(payload, self.colonies)
            self.colonies.append(entity)
            return entity.to_dict()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
