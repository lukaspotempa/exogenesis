import uuid
import random
import math
import numpy as np
from typing import Optional, List, Dict, Any
from models import ColonyModel, Fleet

class Colony:
	"""Wrapper class for colony management"""

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

	def update(self) -> None:
		return

	@classmethod
	def create_colony(cls, payload: dict, existing_colonies: Optional[List["Colony"]] = None) -> "Colony":
		"""Factory: create a Colony from a payload dict.

		This method does not mutate the provided payload; it works on a shallow copy.
		"""
		# work on a copy so callers' dicts aren't mutated
		_payload: Dict[str, Any] = dict(payload)

		if 'id' not in _payload or not _payload.get('id'):
			_payload['id'] = str(uuid.uuid4())

		# If no planet data provided, generate a random planet for colony
		# random vector in [-100, 100] on each axis, and ensure at least
		# 20 units distance from all existing colony planets
		if 'planet' not in _payload or not _payload.get('planet'):
			min_dist = 20.0
			max_attempts = 1000

			def random_pos():
				return np.array([
					random.uniform(-100.0, 100.0),
					random.uniform(-100.0, 100.0),
					random.uniform(-100.0, 100.0),
				], dtype=float)

			existing_positions = []
			if existing_colonies:
				for c in existing_colonies:
					try:
						p = c.colony.planet.position
						existing_positions.append(np.array([p.x, p.y, p.z], dtype=float))
					except Exception:
						continue

			attempts = 0
			pos = random_pos()
			while any(np.linalg.norm(pos - ep) < min_dist for ep in existing_positions):
				attempts += 1
				if attempts > max_attempts:
					raise Exception('Failed to find non-overlapping planet position after many attempts')
				pos = random_pos()

			planet_models = ["Planet_A"]

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
			_payload['planet'] = planet

		colony_model = ColonyModel(**_payload)
		return cls(colony_model)
