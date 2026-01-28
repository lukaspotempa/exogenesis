import uuid
import random
import math
import numpy as np
from typing import Optional, List, Dict, Any
from models import ColonyModel, Fleet, ColonyLevel, OilPump, Vector2, Vector3
import time
from pathlib import Path
import json


_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"
try:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        _CONFIG = json.load(f)
except Exception as exc:
    Exception("Could not read config.json at %s: %s", _CONFIG_PATH, exc)
    _CONFIG = {}

resident_update_interval = _CONFIG.get("resident_update_interval", 3)
colony_distance = _CONFIG.get("colony_min_distance", 20)
space_generation_range = _CONFIG.get("space_generation_range", {"min": -100, "max": 100})

# Resource and growth configuration
ideal_temperature = _CONFIG.get("ideal_temperature", 15.0)
temperature_tolerance = _CONFIG.get("temperature_tolerance", 10.0)
base_growth_rate = _CONFIG.get("base_growth_rate", 20)
water_growth_multiplier = _CONFIG.get("water_growth_multiplier", 1.5)
building_capacity_per_steel = _CONFIG.get("building_capacity_per_steel", 50)
building_capacity_per_oil = _CONFIG.get("building_capacity_per_oil", 30)
initial_resource_storage = _CONFIG.get("initial_resource_storage", 1000.0)

# Colony level thresholds
colony_level_thresholds = _CONFIG.get("colony_level_thresholds", {})

# Oil pump configuration
oil_pump_steel_cost = _CONFIG.get("oil_pump_steel_cost", 500)
oil_pump_max_per_planet = _CONFIG.get("oil_pump_max_per_planet", 3)

# Flanker configuration
flanker_group_size = _CONFIG.get("flanker_group_size", 3)
flanker_steel_cost = _CONFIG.get("flanker_steel_cost", 300)
flanker_oil_cost = _CONFIG.get("flanker_oil_cost", 150)
flanker_spawn_height = _CONFIG.get("flanker_spawn_height", 5)
flanker_spacing = _CONFIG.get("flanker_spacing", 2)
flanker_build_cooldown = _CONFIG.get("flanker_build_cooldown", 30)

# Colony level progression order
COLONY_LEVEL_ORDER = [
	ColonyLevel.Colony,
	ColonyLevel.Settlement,
	ColonyLevel.Township,
	ColonyLevel.Metropolis,
	ColonyLevel.StarportHub
]

class Colony:
	"""Wrapper class for colony management"""

	def __init__(self, colony: ColonyModel):
		self.colony = colony
		self.last_residents_update = time.time()
		self._previous_state = self.colony.dict()
		self._has_changes = False
		self._next_pump_id = 1
		self._action_events = []  # Track action events for this colony
		self.last_flanker_build_time = 0  # Track last time flankers were built

	def to_dict(self):
		return self.colony.dict()

	def add_fleet(self, fleet: Fleet):
		if self.colony.colonyFleet is None:
			self.colony.colonyFleet = []
		self.colony.colonyFleet.append(fleet)
		self._mark_changed()

	def remove_fleet(self, fleet_id: str):
		if not self.colony.colonyFleet:
			return
		old_count = len(self.colony.colonyFleet)
		self.colony.colonyFleet = [f for f in self.colony.colonyFleet if f.id != fleet_id]
		if len(self.colony.colonyFleet) != old_count:
			self._mark_changed()

	def change_residents(self, delta: int):
		self.colony.residents = max(0, self.colony.residents + delta)
		self._mark_changed()

	def update(self) -> None:
		delta = time.time() - self.last_residents_update
		if delta > resident_update_interval:
			# Accumulate resources based on generation rates
			self.accumulate_resources(delta)
			# Produce oil from oil pumps
			self.produce_oil_from_pumps(delta)
			# Calculate and apply resident growth/consumption
			self.increase_residents()
			# Check for colony level upgrades
			self.check_and_upgrade_level()
			# Auto-build structures when resources are available
			self.auto_build_structures()
		return

	def accumulate_resources(self, time_delta: float):
		"""Accumulate resources into storage based on generation rates."""
		resources = self.colony.planet.planetNaturalResources
		
		# Calculate how many tick intervals have passed
		ticks = time_delta / resident_update_interval
		
		# Add generated resources to storage
		resources.oilStorage += resources.oil * ticks
		resources.steelStorage += resources.steel * ticks
		resources.waterStorage += resources.water * ticks
		
		# Clamp to reasonable limits (optional)
		resources.oilStorage = max(0, resources.oilStorage)
		resources.steelStorage = max(0, resources.steelStorage)
		resources.waterStorage = max(0, resources.waterStorage)
		
		self._mark_changed()

	def can_build_oil_pump(self) -> bool:
		"""Check if the colony can build an oil pump."""
		# Must be at least Settlement level
		try:
			current_index = COLONY_LEVEL_ORDER.index(self.colony.colonyLevel)
			# Settlement is index 1
			if current_index < 1:
				return False
		except ValueError:
			return False
		
		# Check if we haven't reached max pumps
		if self.colony.planet.oilPumps is None:
			self.colony.planet.oilPumps = []
		
		if len(self.colony.planet.oilPumps) >= oil_pump_max_per_planet:
			return False
		
		# Check if we have enough steel
		if self.colony.planet.planetNaturalResources.steelStorage < oil_pump_steel_cost:
			return False
		
		return True

	def build_oil_pump(self) -> Optional[OilPump]:
		"""Build an oil pump if possible."""
		if not self.can_build_oil_pump():
			return None
		
		# Deduct steel cost
		self.colony.planet.planetNaturalResources.steelStorage -= oil_pump_steel_cost
		
		# Initialize oilPumps list if needed
		if self.colony.planet.oilPumps is None:
			self.colony.planet.oilPumps = []
		
		# Create oil pump at random position
		# Production rate is based on planet's natural oil generation rate
		pump = OilPump(
			id=str(self._next_pump_id),
			position=Vector2(x=float(random.uniform(-1.0, 1.0)), y=float(random.uniform(-50.0, 50.0))),
			production=self.colony.planet.planetNaturalResources.oil
		)
		
		self._next_pump_id += 1
		self.colony.planet.oilPumps.append(pump)
		self._mark_changed()
		
		# Log the build event
		self._add_action_event(f"built an Oil Pump", "build")
		
		return pump

	def produce_oil_from_pumps(self, time_delta: float):
		"""Produce oil from all oil pumps."""
		if not self.colony.planet.oilPumps:
			return
		
		# Calculate how many tick intervals have passed
		ticks = time_delta / resident_update_interval
		
		# Add oil production from each pump
		for pump in self.colony.planet.oilPumps:
			self.colony.planet.planetNaturalResources.oilStorage += pump.production * ticks
		
		self._mark_changed()

	def calculate_temperature_factor(self) -> float:
		"""Calculate growth multiplier based on temperature proximity to ideal.
		
		Returns a value between 0.1 and 1.0, where:
		- 1.0 = ideal temperature (15°C)
		- Values scale down as temperature moves away from ideal
		- 0.1 = minimum at extreme temperatures
		"""
		temp = self.colony.planet.planetNaturalResources.temperature
		temp_diff = abs(temp - ideal_temperature)
		
		if temp_diff >= temperature_tolerance:
			return 0.1  # Minimum growth factor at extreme temperatures
		
		# Linear interpolation: ideal temp = 1.0, scaling down to 0.1
		return 1.0 - (temp_diff / temperature_tolerance) * 0.9

	def calculate_water_factor(self) -> float:
		"""Calculate growth multiplier based on water GENERATION RATE.
		
		Water generation rate directly impacts growth.
		Returns a value between 0.1 and 2.5, where:
		- Higher water generation = better growth multiplier
		- Low/no water generation = minimal growth
		"""
		water_generation = self.colony.planet.planetNaturalResources.water
		
		if water_generation <= 0:
			return 0.1  # Minimum multiplier with no water generation
		
		# Scale water multiplier based on generation rate
		# Typical water generation is 0.0 to 2.0
		# Scale from 0.1 at 0 water to 2.5 at 2.0+ water
		max_water_generation = 2.0
		min_multiplier = 0.1
		max_multiplier = 2.5
		
		if water_generation >= max_water_generation:
			return max_multiplier
		
		# Linear scaling from min_multiplier to max_multiplier
		scaled_factor = min_multiplier + (water_generation / max_water_generation) * (max_multiplier - min_multiplier)
		return min(scaled_factor, max_multiplier)

	def calculate_building_capacity(self) -> int:
		"""Calculate max population capacity based on steel and oil storage.
		
		Buildings require steel and oil. More resources = higher capacity.
		"""
		resources = self.colony.planet.planetNaturalResources
		
		steel_capacity = resources.steelStorage * building_capacity_per_steel
		oil_capacity = resources.oilStorage * building_capacity_per_oil
		
		# Use the minimum of the two as bottleneck
		return int(min(steel_capacity, oil_capacity))

	def consume_resources(self):
		"""Consume resources based on current population."""
		# Water is no longer consumed - it only acts as a growth multiplier
		# Future: Add consumption for other resources if needed
		pass

	def increase_residents(self):
		"""Calculate and apply resident growth based on multiple resource factors."""
		# Get all growth factors
		temp_factor = self.calculate_temperature_factor()
		water_factor = self.calculate_water_factor()
		
		# Calculate base growth
		growth = base_growth_rate * temp_factor * water_factor
		
		# Check building capacity constraint
		max_capacity = self.calculate_building_capacity()
		
		# If we're at or above capacity, no growth
		if self.colony.residents >= max_capacity and max_capacity > 0:
			growth = 0
		
		# Apply growth (can be negative if conditions are terrible)
		if growth > 0:
			# If close to capacity, reduce growth
			if max_capacity > 0 and self.colony.residents > max_capacity * 0.9:
				capacity_factor = (max_capacity - self.colony.residents) / (max_capacity * 0.1)
				growth *= max(0, capacity_factor)
			
			self.change_residents(int(growth))
		
		self.last_residents_update = time.time()

	def get_next_colony_level(self, current_level: ColonyLevel) -> Optional[ColonyLevel]:
		"""Get the next colony level in the progression."""
		try:
			current_index = COLONY_LEVEL_ORDER.index(current_level)
			if current_index < len(COLONY_LEVEL_ORDER) - 1:
				return COLONY_LEVEL_ORDER[current_index + 1]
		except ValueError:
			pass
		
		return None

	def can_upgrade_to_level(self, target_level: ColonyLevel) -> bool:
		"""Check if colony meets the requirements to upgrade to target level."""
		if target_level.value not in colony_level_thresholds:
			return False
		
		thresholds = colony_level_thresholds[target_level.value]
		resources = self.colony.planet.planetNaturalResources
		
		# Check all requirements
		if self.colony.residents < thresholds.get("residents", 0):
			return False
		if resources.waterStorage < thresholds.get("water_storage", 0):
			return False
		if resources.steelStorage < thresholds.get("steel_storage", 0):
			return False
		if resources.oilStorage < thresholds.get("oil_storage", 0):
			return False
		
		return True

	def check_and_upgrade_level(self):
		"""Check if colony can upgrade to the next level and perform upgrade if possible."""
		next_level = self.get_next_colony_level(self.colony.colonyLevel)
		
		if next_level is None:
			# Already at max level
			return
		
		if self.can_upgrade_to_level(next_level):
			old_level = self.colony.colonyLevel
			self.colony.colonyLevel = next_level
			self._mark_changed()
			
			# Log the level up event
			self._add_action_event(f"upgraded to {next_level.value}", "level-up")
			
			# Optional: Consume resources for upgrade
			if next_level.value in colony_level_thresholds:
				thresholds = colony_level_thresholds[next_level.value]
				resources = self.colony.planet.planetNaturalResources
				
				# Consume a portion of required resources for the upgrade
				resources.waterStorage -= thresholds.get("water_storage", 0) * 0.5
				resources.steelStorage -= thresholds.get("steel_storage", 0) * 0.5
				resources.oilStorage -= thresholds.get("oil_storage", 0) * 0.5
				
				# Ensure storage doesn't go negative
				resources.waterStorage = max(0, resources.waterStorage)
				resources.steelStorage = max(0, resources.steelStorage)
				resources.oilStorage = max(0, resources.oilStorage)
	
	def auto_build_structures(self):
		"""Automatically build structures based on colony needs and resources."""
		# Try to build oil pumps if we can
		while self.can_build_oil_pump():
			pump = self.build_oil_pump()
			if pump is None:
				break  # Failed to build, stop trying
		
		# Try to build flanker groups if we can
		if self.can_build_flanker_group():
			self.build_flanker_group()

	def can_build_flanker_group(self) -> bool:
		"""Check if the colony can build a flanker group."""
		# Check if flanker type is unlocked
		if not self.can_build_fleet_type("Flanker"):
			return False
		
		# Check cooldown
		if time.time() - self.last_flanker_build_time < flanker_build_cooldown:
			return False
		
		# Check max fleet groups limit
		if self.colony.colonyLevel.value in colony_level_thresholds:
			max_groups = colony_level_thresholds[self.colony.colonyLevel.value].get("max_fleet_groups", 1)
			# Count current flanker fleet groups
			if self.colony.colonyFleet:
				flanker_fleets = sum(1 for f in self.colony.colonyFleet if f.type == "Flanker")
				if flanker_fleets >= max_groups:
					return False
		
		# Check if we have enough resources
		resources = self.colony.planet.planetNaturalResources
		if resources.steelStorage < flanker_steel_cost:
			return False
		if resources.oilStorage < flanker_oil_cost:
			return False
		
		return True

	def build_flanker_group(self) -> Optional[Fleet]:
		"""Build a group of flankers (always come in groups of 3)."""
		if not self.can_build_flanker_group():
			return None
		
		# Deduct resources
		resources = self.colony.planet.planetNaturalResources
		resources.steelStorage -= flanker_steel_cost
		resources.oilStorage -= flanker_oil_cost
		
		# Get the planet's world position
		# Frontend will handle positioning relative to the colony base
		planet_pos = self.colony.planet.position
		
		# Spawn at planet center - frontend will offset to proper position
		base_world_pos = Vector3(
			x=planet_pos.x,
			y=planet_pos.y,
			z=planet_pos.z
		)
		
		# Initialize colonyFleet if needed
		if self.colony.colonyFleet is None:
			self.colony.colonyFleet = []
		
		# Create a single fleet entity that represents the flanker group
		# The frontend will handle rendering the formation based on count
		
		group_id = str(uuid.uuid4())[:8]
		
		flanker_fleet = Fleet(
			id=f"flanker_{group_id}",
			type="Flanker",
			label=f"{self.colony.name} Flankers",
			count=flanker_group_size,  # Backend tracks count, frontend renders formation
			position=Vector3(
				x=base_world_pos.x,
				y=base_world_pos.y + flanker_spawn_height,
				z=base_world_pos.z
			),
			velocity=Vector3(x=0.0, y=0.0, z=0.0),
			state="Idle",
			tactic="Offensive",
			hpPool=300.0  # Total HP for the group (100 per ship)
		)
		
		self.colony.colonyFleet.append(flanker_fleet)
		
		# Update last build time
		self.last_flanker_build_time = time.time()
		
		self._mark_changed()
		
		# Log the build event
		self._add_action_event(f"built a Flanker group ({flanker_group_size} ships)", "build")
		
		return flanker_fleet

	def get_unlocked_fleet_types(self) -> List[str]:
		"""Get the list of fleet types unlocked at the current colony level."""
		if self.colony.colonyLevel.value in colony_level_thresholds:
			return colony_level_thresholds[self.colony.colonyLevel.value].get("unlocked_fleet_types", [])
		return []

	def can_build_fleet_type(self, fleet_type: str) -> bool:
		"""Check if a fleet type is unlocked at the current colony level."""
		return fleet_type in self.get_unlocked_fleet_types()

	def get_changes(self) -> Optional[Dict[str, Any]]:
		"""Return changes since last check, or None if no changes."""
		if not self._has_changes:
			return None
		
		current_state = self.colony.dict()
		changes = {}
		
		# Compare current state with previous state
		for key, current_value in current_state.items():
			if key not in self._previous_state or self._previous_state[key] != current_value:
				changes[key] = current_value
		
		changes["id"] = self.colony.id
		
		# Reset change tracking
		self._previous_state = current_state
		self._has_changes = False
		
		return changes

	def _mark_changed(self):
		"""Mark this colony as having changes."""
		self._has_changes = True

	def _add_action_event(self, message: str, event_type: str = "general"):
		"""Add an action event for this colony."""
		import time
		event = {
			"id": str(uuid.uuid4()),
			"timestamp": int(time.time() * 1000),  # milliseconds
			"colonyId": self.colony.id,
			"colonyName": self.colony.name,
			"message": message,
			"type": event_type
		}
		self._action_events.append(event)

	def get_action_events(self) -> List[Dict[str, Any]]:
		"""Get and clear pending action events."""
		events = self._action_events.copy()
		self._action_events.clear()
		return events

	@classmethod
	def create_colony(cls, payload: dict, existing_colonies: Optional[List["Colony"]] = None) -> "Colony":
		"""Factory: create a Colony from a payload dict.

		This method does not mutate the provided payload; it works on a shallow copy.
		"""
		# copy because muteable
		_payload: Dict[str, Any] = dict(payload)

		if 'id' not in _payload or not _payload.get('id'):
			_payload['id'] = str(uuid.uuid4())

		# If no planet data provided, generate a random planet for colony
		if 'planet' not in _payload or not _payload.get('planet'):
			min_dist = colony_distance
			max_attempts = 1000 # This is so we don't loop indefinetly
		
			def random_pos():
				return np.array([
					random.uniform(space_generation_range["min"], space_generation_range["max"]),
					random.uniform(space_generation_range["min"], space_generation_range["max"]),
					random.uniform(space_generation_range["min"], space_generation_range["max"]),
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

			planet_models = ["Planet_A", "Planet_B"]

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
					"oilStorage": initial_resource_storage,
					"steelStorage": initial_resource_storage,
					"waterStorage": initial_resource_storage,
				},
			}
			_payload['planet'] = planet

		colony_model = ColonyModel(**_payload)
		return cls(colony_model)
