from typing import List
from fastapi import HTTPException
import uuid
import random
import math
import numpy as np
from ..models import Planet

from ..models import ColonyModel, Colony


class GameManager:
    """Manages colonies in-memory."""

    def __init__(self):
        self.colonies: List[Colony] = []

    def list_colonies(self) -> List[dict]:
        return [c.to_dict() for c in self.colonies]

    def create_colony(self, payload: dict) -> dict:
        try:
            if 'id' not in payload or not payload.get('id'):
                payload['id'] = str(uuid.uuid4())

            # If no planet data provided, generate a random planet for colony
            # random vector in [-100, 100] on each axis, and ensure at least
            # 20 units distance from all existing colony planets
            if 'planet' not in payload or not payload.get('planet'):
                min_dist = 20.0
                max_attempts = 1000

                def random_pos():
                    return np.array([
                        random.uniform(-100.0, 100.0),
                        random.uniform(-100.0, 100.0),
                        random.uniform(-100.0, 100.0),
                    ], dtype=float)

                existing_positions = []
                for c in self.colonies:
                    try:
                        p = c.colony.planet.position
                        existing_positions.append(np.array([p.x, p.y, p.z], dtype=float))
                    except Exception:
                        # Skip colonies with malformed/missing planet data
                        continue

                attempts = 0
                pos = random_pos()
                while any(np.linalg.norm(pos - ep) < min_dist for ep in existing_positions):
                    attempts += 1
                    if attempts > max_attempts:
                        raise Exception('Failed to find non-overlapping planet position after many attempts')
                    pos = random_pos()

                # Planet models list
                planet_models = ["PlanetA"]

                planet = {
                    "position": {"x": float(pos[0]), "y": float(pos[1]), "z": float(pos[2])},
                    "scale": float(random.uniform(0.7, 1.3)),
                    "rot": {
                        "x": float(random.uniform(0.0, math.tau if hasattr(math, 'tau') else 2 * math.pi)),
                        "y": float(random.uniform(0.0, math.tau if hasattr(math, 'tau') else 2 * math.pi)),
                        "z": float(random.uniform(0.0, math.tau if hasattr(math, 'tau') else 2 * math.pi)),
                    },
                    "planetModelName": random.choice(planet_models),
                    "planetMainBase": {"x": float(random.uniform(-1.0, 1.0)), "y": float(random.uniform(-50.0, 50))},
                    "planetNaturalResources": {
                        "oil": float(random.uniform(0.0, 2.0)),
                        "steel": float(random.uniform(0.0, 2.0)),
                        "water": float(random.uniform(0.0, 2.0)),
                        "temperature": float(random.uniform(0.0, 30.0)),
                    },
                }

                payload['planet'] = planet

            colony_model = ColonyModel(**payload)
            entity = Colony(colony_model)
            self.colonies.append(entity)
            return entity.to_dict()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
