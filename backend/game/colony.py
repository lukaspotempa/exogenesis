import uuid
import random
import math
import numpy as np
from typing import Optional, List, Dict, Any, cast, Union
from models import ColonyModel, Fleet, ColonyLevel, ColonyTrait, OilPump, SteelFactory, Vector2, Vector3, FleetTarget
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
planet_model_radius = _CONFIG.get("planet_model_radius", 1.0)
space_generation_range = _CONFIG.get("space_generation_range", {"min": -100, "max": 100})

# Resource and growth configuration
ideal_temperature = _CONFIG.get("ideal_temperature", 15.0)
temperature_tolerance = _CONFIG.get("temperature_tolerance", 10.0)
base_growth_rate = _CONFIG.get("base_growth_rate", 20)
water_growth_multiplier = _CONFIG.get("water_growth_multiplier", 1.5)
building_capacity_per_steel = _CONFIG.get("building_capacity_per_steel", 50)
building_capacity_per_oil = _CONFIG.get("building_capacity_per_oil", 30)
initial_steel_storage = _CONFIG.get("initial_steel_storage", 600.0)
initial_oil_storage = _CONFIG.get("initial_oil_storage", 250.0)
initial_water_storage = _CONFIG.get("initial_water_storage", 300.0)

# Colony level thresholds
colony_level_thresholds = _CONFIG.get("colony_level_thresholds", {})

# Oil pump configuration
oil_pump_steel_cost = _CONFIG.get("oil_pump_steel_cost", 500)
oil_pump_max_per_planet = _CONFIG.get("oil_pump_max_per_planet", 3)

# Steel factory configuration
steel_factory_oil_cost = _CONFIG.get("steel_factory_oil_cost", 200)
steel_factory_max_per_planet = _CONFIG.get("steel_factory_max_per_planet", 3)

# Building placement configuration
min_building_distance = _CONFIG.get("min_building_distance", 12.0)

# Flanker configuration
flanker_group_size = _CONFIG.get("flanker_group_size", 3)
flanker_steel_cost = _CONFIG.get("flanker_steel_cost", 300)
flanker_oil_cost = _CONFIG.get("flanker_oil_cost", 150)
flanker_spawn_height = _CONFIG.get("flanker_spawn_height", 5)
flanker_spacing = _CONFIG.get("flanker_spacing", 2)
flanker_build_cooldown = _CONFIG.get("flanker_build_cooldown", 30)

# Fighter configuration
fighter_group_size = _CONFIG.get("fighter_group_size", 5)
fighter_steel_cost = _CONFIG.get("fighter_steel_cost", 200)
fighter_oil_cost = _CONFIG.get("fighter_oil_cost", 100)
fighter_build_cooldown = _CONFIG.get("fighter_build_cooldown", 25)

# Bomber configuration
bomber_group_size = _CONFIG.get("bomber_group_size", 2)
bomber_steel_cost = _CONFIG.get("bomber_steel_cost", 400)
bomber_oil_cost = _CONFIG.get("bomber_oil_cost", 200)
bomber_build_cooldown = _CONFIG.get("bomber_build_cooldown", 40)

# Scout configuration
scout_group_size = _CONFIG.get("scout_group_size", 1)
scout_steel_cost = _CONFIG.get("scout_steel_cost", 100)
scout_oil_cost = _CONFIG.get("scout_oil_cost", 50)
scout_build_cooldown = _CONFIG.get("scout_build_cooldown", 15)

# Attack parking spot configuration
attack_parking_spot_distance = _CONFIG.get("attack_parking_spot_distance", 20.0)
attack_parking_spot_spread = _CONFIG.get("attack_parking_spot_spread", 5.0)

# Fleet awareness configuration
fleet_awareness_radius = _CONFIG.get("fleet_awareness_radius", 35.0)
fleet_engagement_priority_distance = _CONFIG.get("fleet_engagement_priority_distance", 20.0)

# Base targeting height (offset above surface for projectile aiming)
base_target_height = _CONFIG.get("base_target_height", 2.0)

# Colony defense stats per level
colony_defense_stats = _CONFIG.get("colony_defense_stats", {})

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
		if self.colony.owner_id is None:
			self.colony.owner_id = self.colony.id
		
		# Apply defense stats (HP) from config for the current colony level
		defense = colony_defense_stats.get(self.colony.colonyLevel.value, {})
		initial_hp = defense.get("base_hp", 1000.0)
		if self.colony.hp == 1000.0 and self.colony.max_hp == 1000.0:
			# Only override defaults — don't overwrite already-customized HP
			self.colony.hp = initial_hp
			self.colony.max_hp = initial_hp
		
		self.last_residents_update = time.time()
		self._previous_state = self.colony.dict()
		self._has_changes = False
		self._next_pump_id = 1
		self._next_factory_id = 1
		self._action_events = []  # Track action events for this colony
		self.last_structure_build_time = 0 # Track last time any structure was built
		self.last_flanker_build_time = 0  # Track last time flankers were built
		self.last_fighter_build_time = 0 
		self.last_bomber_build_time = 0
		self.last_scout_build_time = 0
		self._fleet_patrol_cooldowns = {}  # Track when each fleet last got new patrol waypoints
		self._fleet_waypoint_timers = {}  # Track when each waypoint was set for time-based rotation
		
		# Colony-level attack coordination
		self.attack_target_colony_id: Optional[str] = None  # ID of colony being attacked
		self.attack_decision_time = 0.0  # Last time colony made attack decision
		self.attack_decision_cooldown = 10.0  # Seconds between attack decisions
		self._fleet_parking_spots: Dict[str, Vector3] = {}  # fleet_id -> assigned parking spot position
		self._all_colonies_cache: Optional[List['Colony']] = None  # Temporary cache for all colonies

	def to_dict(self):
		return self.colony.dict()

	def _distance_v2(self, p1: Vector2, p2: Vector2) -> float:
		"""Calculate euclidean distance between two Vector2 points."""
		return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

	def _distance_v3(self, p1: Vector3, p2: Vector3) -> float:
		"""Calculate euclidean distance between two Vector3 points."""
		return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

	def _is_position_valid(self, position: Vector2, min_dist: float) -> bool:
		"""Check if a position is valid (not too close to other structures)."""
		# Check base
		base = self.colony.planet.planetMainBase
		if self._distance_v2(position, base) < min_dist:
			return False
		
		# Check oil pumps
		if self.colony.planet.oilPumps:
			for pump in self.colony.planet.oilPumps:
				if self._distance_v2(position, pump.position) < min_dist:
					return False
		
		# Check steel factories
		if self.colony.planet.steelFactories:
			for fac in self.colony.planet.steelFactories:
				if self._distance_v2(position, fac.position) < min_dist:
					return False
					
		return True

	def _get_random_valid_position(self) -> Optional[Vector2]:
		"""Try to find a valid position for a new building."""
		for _ in range(20):  # Try 20 times
			# Same generation range as original: X: -1 to 1, Y: -50 to 50
			pos = Vector2(
				x=float(random.uniform(-1.0, 1.0)), 
				y=float(random.uniform(-50.0, 50.0))
			)
			if self._is_position_valid(pos, min_building_distance):
				return pos
		return None

	def add_fleet(self, fleet: Fleet):
		if self.colony.colonyFleet is None:
			self.colony.colonyFleet = []
		self.colony.colonyFleet.append(fleet)
		self._mark_changed()

	def remove_fleet(self, fleet_id: str):
		"""Remove a specific fleet by ID."""
		if not self.colony.colonyFleet:
			return
		
		# Store old list for debugging potential issues
		old_count = len(self.colony.colonyFleet)
		
		# Filter out only the fleet with matching ID
		self.colony.colonyFleet = [f for f in self.colony.colonyFleet if f.id != fleet_id]
		
		new_count = len(self.colony.colonyFleet)
		removed_count = old_count - new_count
		
		# Defensive check: warn if we removed more than one fleet (shouldn't happen)
		if removed_count > 1:
			print(f"WARNING: Removed {removed_count} fleets when trying to remove fleet {fleet_id}")
		
		if removed_count > 0:
			self._mark_changed()

	def change_residents(self, delta: int):
		self.colony.residents = max(0, self.colony.residents + delta)
		self._mark_changed()

	def update(self, delta_time: Optional[float] = None, all_colonies: Optional[List['Colony']] = None) -> None:
		"""Update colony state, including fleets.
		
		Args:
			delta_time: Time since last tick in seconds (for fleet movement).
			all_colonies: List of all colonies in the game (for combat/interactions).
		"""
		if delta_time is None:
			delta_time = 0.5  # Default tick rate
		
		# Cache all colonies for fleet spawning
		self._all_colonies_cache = all_colonies
		
		# Colony-level attack decision making
		if all_colonies:
			# Check if we should initiate a new attack
			if self._should_initiate_attack(all_colonies):
				target = self._select_attack_target(all_colonies)
				if target:
					self._order_colony_wide_attack(target, all_colonies)
			
			# Check if current attack target is still valid
			if self.attack_target_colony_id:
				target_still_exists = False
				my_owner = self.colony.owner_id
				for other in all_colonies:
					if other.colony.id == self.attack_target_colony_id:
						other_owner = other.colony.owner_id if other.colony.owner_id else other.colony.id
						if other_owner != my_owner:
							target_still_exists = True
						break
				
				# If target no longer exists or was conquered, clear attack
				if not target_still_exists:
					self.attack_target_colony_id = None
					self._fleet_parking_spots = {}
		
		# Handle combat behavior first
		if all_colonies:
			self.update_combat(delta_time, all_colonies)
			
			# Check if ongoing attack should be terminated
			if self.attack_target_colony_id:
				# Check if any fleets are still actively attacking this target
				fleets_attacking_target = [
					f for f in (self.colony.colonyFleet or [])
					if f.target and f.target.id == self.attack_target_colony_id
				]
				
				# If no fleets are attacking the target anymore, clear the attack
				if not fleets_attacking_target:
					self.attack_target_colony_id = None
					self._fleet_parking_spots = {}
				else:
					# Reinforce: Check for newly idle/patrolling fleets that should join the attack
					for target_col in all_colonies:
						if target_col.colony.id == self.attack_target_colony_id:
							self._reinforce_attack(target_col, all_colonies)
							break

		# Update fleets every tick (movement and behavior)
		self.update_fleets(delta_time, all_colonies)
		
		# Check if enough time has passed for resource/resident updates
		time_since_last_update = time.time() - self.last_residents_update
		if time_since_last_update > resident_update_interval:
			# Accumulate resources based on generation rates
			self.accumulate_resources(time_since_last_update)
			# Produce oil from oil pumps
			self.produce_oil_from_pumps(time_since_last_update)
			# Produce steel from steel factories
			self.produce_steel_from_factories(time_since_last_update)
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
		
		# Validate cooldown (safety check, though usually handled in auto_build)
		# But since this can be called manually or in a loop, let's update timestamp here
		self.last_structure_build_time = time.time()

		# Deduct steel cost
		self.colony.planet.planetNaturalResources.steelStorage -= oil_pump_steel_cost
		
		# Initialize oilPumps list if needed
		if self.colony.planet.oilPumps is None:
			self.colony.planet.oilPumps = []
		
		# Find a valid position
		position = self._get_random_valid_position()
		if position is None:
			# Could not find a valid position (too crowded)
			# Even if we can afford it, we can't build it
			# Refund cost if we deducted it? Or safer to check position before deducting
			# Let's revert the cost deduction
			self.colony.planet.planetNaturalResources.steelStorage += oil_pump_steel_cost
			return None

		# Create oil pump at validated position
		# Production rate is based on planet's natural oil generation rate
		pump = OilPump(
			id=str(self._next_pump_id),
			position=position,
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

	def can_build_steel_factory(self) -> bool:
		"""Check if the colony can build a steel factory."""
		# Must be at least Settlement level
		try:
			current_index = COLONY_LEVEL_ORDER.index(self.colony.colonyLevel)
			# Settlement is index 1
			if current_index < 1:
				return False
		except ValueError:
			return False
		
		# Check if we haven't reached max factories
		if self.colony.planet.steelFactories is None:
			self.colony.planet.steelFactories = []
		
		try:
			if len(self.colony.planet.steelFactories) >= steel_factory_max_per_planet:
				return False
		except TypeError:
			# Handle case where steelFactories might be implicitly None or invalid
			self.colony.planet.steelFactories = []
		
		# Check if we have enough oil
		if self.colony.planet.planetNaturalResources.oilStorage < steel_factory_oil_cost:
			return False
		
		return True

	def build_steel_factory(self) -> Optional[SteelFactory]:
		"""Build a steel factory if possible."""
		if not self.can_build_steel_factory():
			return None
		
		# Update timestamp
		self.last_structure_build_time = time.time()
		
		# Deduct oil cost
		self.colony.planet.planetNaturalResources.oilStorage -= steel_factory_oil_cost
		
		# Initialize steelFactories list if needed
		if self.colony.planet.steelFactories is None:
			self.colony.planet.steelFactories = []
		
		# Find a valid position
		position = self._get_random_valid_position()
		if position is None:
			# Could not find a valid position (too crowded)
			# Revert cost
			self.colony.planet.planetNaturalResources.oilStorage += steel_factory_oil_cost
			return None

		# Create steel factory at validated position
		# Production rate is based on planet's natural steel generation rate
		factory = SteelFactory(
			id=str(self._next_factory_id),
			# Use the same positioning logic as oil pumps or vary it?
			# Oil pumps use: position=Vector2(x=float(random.uniform(-1.0, 1.0)), y=float(random.uniform(-50.0, 50.0)))
			position=position,
			production=self.colony.planet.planetNaturalResources.steel
		)
		
		self._next_factory_id += 1
		self.colony.planet.steelFactories.append(factory)
		self._mark_changed()
		
		# Log the build event
		self._add_action_event(f"built a Steel Factory", "build")
		
		return factory

	def produce_steel_from_factories(self, time_delta: float):
		"""Produce steel from all steel factories."""
		if not self.colony.planet.steelFactories:
			return
		
		# Calculate how many tick intervals have passed
		ticks = time_delta / resident_update_interval
		
		# Add steel production from each factory
		for factory in self.colony.planet.steelFactories:
			self.colony.planet.planetNaturalResources.steelStorage += factory.production * ticks
		
		self._mark_changed()
	def _get_planet_base_position(self) -> Vector3:
		"""Calculate the world position of the colony's main base."""
		# Constants from Colony.tsx
		COORDINATE_SCALE = 50.0
		
		# Get base coordinates (2D pseudo-spherical)
		base_x = self.colony.planet.planetMainBase.x
		base_y = self.colony.planet.planetMainBase.y
		
		# Convert to spherical direction (Unit Vector on Sphere)
		# From frontend:
		# const longitude = (x / COORDINATE_SCALE) * Math.PI * 2;
		# const latitude = (y / COORDINATE_SCALE) * Math.PI;
		longitude = (base_x / COORDINATE_SCALE) * math.pi * 2
		latitude = (base_y / COORDINATE_SCALE) * math.pi
		
		# Calculate unit vector (local space, unrotated)
		# x = cos(lat) * cos(long)
		# y = sin(lat)
		# z = cos(lat) * sin(long)
		ux = math.cos(latitude) * math.cos(longitude)
		uy = math.sin(latitude)
		uz = math.cos(latitude) * math.sin(longitude)
		
		# Apply Planet Rotation (Euler XYZ)
		# We need to rotate this vector by rot.x, rot.y, rot.z
		# Note: Frontend renders using raycast with unrotated direction vector, 
		# so we should NOT apply rotation here to match visual position.
		# Ideally both should support rotation, but for now we match frontend.
		x3 = ux
		y3 = uy
		z3 = uz
		
		# Apply Scale
		scale = self.colony.planet.scale
		# The planet radius is (scale * planet_model_radius)
		final_radius = scale * planet_model_radius
		
		x_final = x3 * final_radius
		y_final = y3 * final_radius
		z_final = z3 * final_radius
		
		# Add Planet World Position
		pos = self.colony.planet.position
		return Vector3(
			x=pos.x + x_final,
			y=pos.y + y_final,
			z=pos.z + z_final
		)

	def _get_base_target_position(self) -> Vector3:
		"""Get an elevated target position above the colony base for attack targeting.
		
		Returns the base surface position offset outward along the surface normal
		so projectiles aim at the flag / visual center of the settlement.
		The height is multiplied by the planet's scale so it remains correct
		regardless of planet size (structures are rendered inside the scaled group).
		"""
		base_pos = self._get_planet_base_position()
		planet_pos = self.colony.planet.position
		
		# Surface normal = direction from planet center to base
		nx = base_pos.x - planet_pos.x
		ny = base_pos.y - planet_pos.y
		nz = base_pos.z - planet_pos.z
		n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
		
		if n_len > 0.001:
			nx, ny, nz = nx/n_len, ny/n_len, nz/n_len
		else:
			nx, ny, nz = 0, 1, 0
		
		# Scale the height offset so it matches the visual flag height on any
		# planet size (structures live inside the scaled planet group)
		scaled_height = base_target_height * self.colony.planet.scale
		
		return Vector3(
			x=base_pos.x + nx * scaled_height,
			y=base_pos.y + ny * scaled_height,
			z=base_pos.z + nz * scaled_height
		)

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
			
			# Apply defense stats (HP) for the new level
			defense = colony_defense_stats.get(next_level.value, {})
			new_max_hp = defense.get("base_hp", self.colony.max_hp)
			self.colony.max_hp = new_max_hp
			# Heal to new max on upgrade
			self.colony.hp = new_max_hp
			
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
		"""Automatically build structures based on colony needs, resources, and trait."""
		# Check global build cooldown (prevent instant spam)
		# Allow at least 2 seconds between builds
		if time.time() - self.last_structure_build_time < 2.0:
			return
			
		# Add "noise" - 30% chance to do nothing this tick even if ready
		if random.random() < 0.3:
			return

		trait = self.colony.trait
		
		# Helper to try building any economic structure
		def try_build_economy():
			# Shuffle order to not prioritize one over another always
			options = ["pump", "factory"]
			random.shuffle(options)
			
			for opt in options:
				if opt == "pump" and self.can_build_oil_pump():
					self.build_oil_pump()
					return True
				elif opt == "factory" and self.can_build_steel_factory():
					self.build_steel_factory()
					return True
			return False
		
		# Helper to try building any fleet type
		def try_build_fleet():
			# List of fleet types to try, shuffled
			options = ["Flanker", "Fighter", "Bomber", "Scout"]
			random.shuffle(options)
			
			for opt in options:
				if opt == "Flanker" and self.can_build_flanker_group():
					self.build_flanker_group()
					return True
				elif opt == "Fighter" and self.can_build_fighter_group():
					self.build_fighter_group()
					return True
				elif opt == "Bomber" and self.can_build_bomber_group():
					self.build_bomber_group()
					return True
				elif opt == "Scout" and self.can_build_scout_group():
					self.build_scout_group()
					return True
			return False

		# Pacifist: Only builds economic structures, never fleets
		if trait == ColonyTrait.Pacifist.value:
			try_build_economy()
			return  # Never build fleets
		
		# Economic: Heavily favors economic structures (80% chance to prioritize economy)
		elif trait == ColonyTrait.Economic.value:
			if random.random() < 0.8:
				if try_build_economy():
					return
			
			# If didn't build economy (either chance or cannot), maybe build fleet
			if random.random() < 0.2:
				try_build_fleet()
		
		# Aggressive: Heavily favors fleets (70% chance to prioritize fleets)
		elif trait == ColonyTrait.Aggressive.value:
			# Prioritize fleet building
			if random.random() < 0.7:
				if not try_build_fleet():
					# Fallback to economy if can't build fleet
					try_build_economy()
			# Still build some economic structures (30%)
			else:
				if not try_build_economy():
					try_build_fleet()
		
		# Defensive: Balanced approach (50/50 split between economy and defense)
		elif trait == ColonyTrait.Defensive.value:
			# Random choice between building economic or military
			if random.random() < 0.5:
				# Build economic
				if not try_build_economy():
					# Fallback to fleet if can't build economy
					try_build_fleet()
			else:
				# Build fleet
				if not try_build_fleet():
					# Fallback to economic if can't build fleet
					try_build_economy()
		
		# Default behavior if no trait matched
		else:
			# Balanced approach. Try to build one thing.
			if random.random() < 0.5:
				if not try_build_economy():
					try_build_fleet()
			else:
				if not try_build_fleet():
					try_build_economy()

	def update_fleets(self, delta_time: float, all_colonies: Optional[List['Colony']] = None):
		"""Update all fleet positions and behaviors."""
		if not self.colony.colonyFleet:
			return
		
		# Create a copy to prevent modification-during-iteration issues
		fleets_to_update = list(self.colony.colonyFleet)
		
		for fleet in fleets_to_update:
			# Verify fleet still exists (might have been removed during combat)
			if fleet not in self.colony.colonyFleet:
				continue
				
			# First, check awareness - fleets should be aware of their surroundings
			if all_colonies and fleet.state != "Attacking":
				self._update_fleet_awareness(fleet, all_colonies)
			
			self._update_fleet_movement(fleet, delta_time, all_colonies)
			self._update_fleet_behavior(fleet, all_colonies)

	def _project_position_to_orbit(self, position: Vector3, min_radius_only: bool = False) -> Vector3:
		"""Project a position onto the safe orbit shell around the planet."""
		planet_pos = self.colony.planet.position
		
		# specific vector from planet center to position
		dx = position.x - planet_pos.x
		dy = position.y - planet_pos.y
		dz = position.z - planet_pos.z
		
		dist = math.sqrt(dx*dx + dy*dy + dz*dz)
		if dist < 0.001:
			dx, dy, dz = 0, 1, 0
			dist = 0.001 # Fix div by zero risk properly
			
		# Safe Orbit Radius:
		# Planet Scale * Base Radius (from config) * Safety(1.1) + Fly Altitude (3.0)
		orbit_radius = self.colony.planet.scale * planet_model_radius * 1.1 + 3.0
		
		# If we only want to ensure minimum radius (for leaving orbit)
		if min_radius_only:
			if dist >= orbit_radius:
				return position
			# Otherwise push out to radius
		
		scale_factor = orbit_radius / dist
		
		return Vector3(
			x=planet_pos.x + dx * scale_factor,
			y=planet_pos.y + dy * scale_factor,
			z=planet_pos.z + dz * scale_factor
		)

	def _update_fleet_movement(self, fleet: Fleet, delta_time: float, all_colonies: Optional[List['Colony']] = None):
		"""Update fleet velocity vector towards current waypoint.
		
		All positions and waypoints are in WORLD SPACE.
		Backend calculates velocity toward waypoint.
		"""
		# Update actual position based on velocity from previous tick
		# This makes the backend authoritative on position
		if fleet.velocity.x != 0 or fleet.velocity.y != 0 or fleet.velocity.z != 0:
			# Predict next position
			next_x = fleet.position.x + fleet.velocity.x * delta_time
			next_y = fleet.position.y + fleet.velocity.y * delta_time
			next_z = fleet.position.z + fleet.velocity.z * delta_time
			
			# Orbit Constraint Strategy:
			# 1. Patrol/Idle: Strict constraint (stick to shell)
			# 2. Attack (Moving remote): Min-radius constraint (don't clip planet)
			use_min_radius = False
			if fleet.state == "Moving" and fleet.target and fleet.target.id:
				use_min_radius = True
			
			# Global Planet Collision Avoidance (Clip Check)
			# If we are moving interstellar, check if we are clipping ANY planet
			# If so, push us out.
			if use_min_radius and all_colonies:
				for c in all_colonies:
					p_pos = c.colony.planet.position
					p_scale = c.colony.planet.scale
					p_rad = p_scale * planet_model_radius * 1.1 + 3.0 # Safe radius
					
					p_dx = next_x - p_pos.x
					p_dy = next_y - p_pos.y
					p_dz = next_z - p_pos.z
					p_dist = math.sqrt(p_dx*p_dx + p_dy*p_dy + p_dz*p_dz)
					
					if p_dist < p_rad:
						# Collision! Push out.
						if p_dist < 0.001: p_dist = 0.001
						scale = p_rad / p_dist
						next_x = p_pos.x + p_dx * scale
						next_y = p_pos.y + p_dy * scale
						next_z = p_pos.z + p_dz * scale

			constrained_pos = self._project_position_to_orbit(
				Vector3(x=next_x, y=next_y, z=next_z),
				min_radius_only=use_min_radius
			)
			
			fleet.position.x = constrained_pos.x
			fleet.position.y = constrained_pos.y
			fleet.position.z = constrained_pos.z

		if not fleet.waypoints or len(fleet.waypoints) == 0:
			# No waypoints, fleet is stationary
			if fleet.velocity.x != 0 or fleet.velocity.y != 0 or fleet.velocity.z != 0:
				fleet.velocity = Vector3(x=0.0, y=0.0, z=0.0)
				self._mark_changed()
			return
		
		# Get current target waypoint (in world space)
		target_waypoint = fleet.waypoints[0]
		
		# Calculate direction to target in world space from CURRENT position
		dx = target_waypoint.x - fleet.position.x
		dy = target_waypoint.y - fleet.position.y
		dz = target_waypoint.z - fleet.position.z
		distance = math.sqrt(dx*dx + dy*dy + dz*dz)
		
		# Check if reached waypoint (within a small tolerance)
		arrival_threshold = 1.0
		
		if distance <= arrival_threshold:
			# Reached waypoint
			self._mark_changed()
			
			# Remove the current waypoint
			if fleet.waypoints:
				reached_wp = fleet.waypoints.pop(0)
				
				# For Patrolling, cycle it back to the end
				if fleet.state == "Patrolling":
					fleet.waypoints.append(reached_wp)

			# Behavior depends on state
			if fleet.state == "Moving" and fleet.target and fleet.target.id:
				# Only switch to Attacking if we have reached the FINAL waypoint
				if not fleet.waypoints:
					fleet.velocity = Vector3(x=0.0, y=0.0, z=0.0)
					fleet.state = "Attacking"
					fleet.isAttacking = True
					fleet.combatWarmup = 2.0  # Set warmup delay
					return

			# If waypoints empty now, stop
			if not fleet.waypoints:
				fleet.velocity = Vector3(x=0.0, y=0.0, z=0.0)
				if fleet.state == "Moving":
					fleet.state = "Idle"
				return

			# Update target to new first waypoint for velocity calculation
			target_waypoint = fleet.waypoints[0]
			dx = target_waypoint.x - fleet.position.x
			dy = target_waypoint.y - fleet.position.y
			dz = target_waypoint.z - fleet.position.z
			distance = math.sqrt(dx*dx + dy*dy + dz*dz)
		
		# Calculate velocity towards waypoint (in world space)
		if distance > 0:
			speed = fleet.speed if fleet.speed else 5.0
			
			# Global Collision Avoidance (Steering)
			# Calculate direction that avoids planets on the path
			if all_colonies:
				steer_dir = self._get_collision_free_direction(fleet.position, target_waypoint, all_colonies)
				dir_x = steer_dir.x
				dir_y = steer_dir.y
				dir_z = steer_dir.z
			else:
				dir_x = dx / distance
				dir_y = dy / distance
				dir_z = dz / distance

			new_velocity = Vector3(
				x=dir_x * speed,
				y=dir_y * speed,
				z=dir_z * speed
			)
			
			# Only update velocity if it changed significantly (reduces broadcasts)
			if (abs(new_velocity.x - fleet.velocity.x) > 0.01 or 
				abs(new_velocity.y - fleet.velocity.y) > 0.01 or 
				abs(new_velocity.z - fleet.velocity.z) > 0.01):
				fleet.velocity = new_velocity
				self._mark_changed()

	def _update_fleet_behavior(self, fleet: Fleet, all_colonies: Optional[List['Colony']] = None):
		"""Update fleet behavior based on state and trait."""
		# If Attacking, we are managed by update_combat
		if fleet.state == "Attacking":
			return

		# Don't interfere with fleets that are part of a coordinated attack
		if fleet.target and fleet.target.id == self.attack_target_colony_id:
			# This fleet is part of the attack, let it continue
			return
		
		# Only generate new waypoints for idle/patrolling fleets with no waypoints
		if fleet.state not in ["Idle", "Patrolling"]:
			return
		
		# Check if this fleet already has waypoints (still executing patrol)
		if fleet.waypoints is not None and len(fleet.waypoints) > 0:
			return
		
		# Check cooldown - don't generate new waypoints too frequently
		current_time = time.time()
		last_patrol_time = self._fleet_patrol_cooldowns.get(fleet.id, 0)
		if current_time - last_patrol_time < 3.0:  # 3 second cooldown between patrols
			return
		
		# Update the cooldown timer
		self._fleet_patrol_cooldowns[fleet.id] = current_time
		
		# Note: Awareness checks now handled in _update_fleet_awareness
		# which is called before this method in update_fleets

		# Pacifist colonies don't move fleets aggressively
		if self.colony.trait == ColonyTrait.Pacifist.value:
			# Just stay near home with minimal patrol
			self._set_patrol_waypoints(fleet, all_colonies, patrol_distance=0.5)
			return
		
		# Other colonies patrol actively but stay near home base
		# Get patrol radius from config based on fleet type
		fleet_stats = _CONFIG.get("fleet_stats", {}).get(fleet.type, {})
		patrol_radius = fleet_stats.get("patrol_radius", 1.0)
		
		self._set_patrol_waypoints(fleet, all_colonies, patrol_distance=patrol_radius)

	def _set_patrol_waypoints(self, fleet: Fleet, all_colonies: Optional[List['Colony']], patrol_distance: float = 1.0):
		"""Generate patrol waypoints in a circle around the home position.
		
		All coordinates are in WORLD SPACE.
		Waypoints are generated around the fleet's home position (spawn point).
		"""
		if not fleet.homePosition:
			# Use current position as home if not set
			fleet.homePosition = Vector3(
				x=fleet.position.x,
				y=fleet.position.y,
				z=fleet.position.z
			)
		
		# Cap patrol distance to keep fleets near their home base
		patrol_distance = min(patrol_distance, 50.0)
		
		# Generate waypoints in a roughly circular patrol pattern around HOME position
		# We need to orient the circle tangent to the planet surface if possible,
		# or just use a horizontal circle if homePosition is well above the planet.
		# Given they spawn above the base, "Horizontal" (XZ) might cut through the planet 
		# if the base is on the side.
		
		# Better strategy: Define the "Up" vector as (Home - PlanetCenter).
		# Then generate a circle in the plane perpendicular to "Up".
		
		planet_pos = self.colony.planet.position
		hx = fleet.homePosition.x - planet_pos.x
		hy = fleet.homePosition.y - planet_pos.y
		hz = fleet.homePosition.z - planet_pos.z
		
		# Normalize Up vector
		h_len = math.sqrt(hx*hx + hy*hy + hz*hz)
		if h_len > 0.001:
			ux, uy, uz = hx/h_len, hy/h_len, hz/h_len
		else:
			ux, uy, uz = 0, 1, 0
			
		# Find arbitrary tangent vectors (Right and Forward) perpendicular to Up
		# If Up is roughly Y, use X as temp right.
		if abs(uy) > 0.9:
			# Up is close to Y axis, use X as reference
			rx, ry, rz = 1, 0, 0
		else:
			# Up is not Y, use Y as reference
			rx, ry, rz = 0, 1, 0
			
		# Right = Cross(Reference, Up)
		# Rx = Ry*Uz - Rz*Uy
		# Ry = Rz*Ux - Rx*Uz
		# Rz = Rx*Uy - Ry*Ux
		t_rx = ry*uz - rz*uy
		t_ry = rz*ux - rx*uz
		t_rz = rx*uy - ry*ux
		
		# Normalize Right
		t_len = math.sqrt(t_rx*t_rx + t_ry*t_ry + t_rz*t_rz)
		if t_len > 0.001:
			t_rx, t_ry, t_rz = t_rx/t_len, t_ry/t_len, t_rz/t_len
		else:
			t_rx, t_ry, t_rz = 1, 0, 0
			
		# Forward = Cross(Up, Right)
		fx = uy*t_rz - uz*t_ry
		fy = uz*t_rx - ux*t_rz
		fz = ux*t_ry - uy*t_rx
		
		# Normalize Forward (should already be normalized)
		f_len = math.sqrt(fx*fx + fy*fy + fz*fz)
		if f_len > 0.001:
			fx, fy, fz = fx/f_len, fy/f_len, fz/f_len
			
		final_waypoints = []
		target_points = []
		num_waypoints = 8  # More waypoints for smoother circle
		
		center_x = fleet.homePosition.x
		center_y = fleet.homePosition.y  
		center_z = fleet.homePosition.z
		
		# First generate the target points on the circle
		for i in range(num_waypoints):
			angle = (i * 2 * math.pi / num_waypoints)
			
			# Circle point in local 2D plane (Right, Forward)
			cos_a = math.cos(angle)
			sin_a = math.sin(angle)
			
			# p = Center + Right*cos(a)*R + Forward*sin(a)*R
			wx = center_x + (t_rx * cos_a + fx * sin_a) * patrol_distance
			wy = center_y + (t_ry * cos_a + fy * sin_a) * patrol_distance
			wz = center_z + (t_rz * cos_a + fz * sin_a) * patrol_distance
			
			# Project this tangent point onto the Safe Orbit Shell
			# This ensures the waypoint itself is not inside/outside the orbit
			wp_projected = self._project_position_to_orbit(Vector3(x=wx, y=wy, z=wz))
			target_points.append(wp_projected)

		# Now generate valid paths between points
		# Start from current fleet position to first point
		current_start = fleet.position
		
		# Filter out home colony from collision detection for patrol paths
		# Patrol waypoints orbit the home planet, so it shouldn't be treated as an obstacle
		other_colonies = [c for c in all_colonies if c.colony.id != self.colony.id] if all_colonies else None
		
		# Add path to first point
		if other_colonies:
			path = self._generate_path_waypoints(current_start, target_points[0], other_colonies)
			final_waypoints.extend(path)
		else:
			final_waypoints.append(target_points[0])
			
		# Add paths between subsequent points
		for i in range(len(target_points) - 1):
			p1 = target_points[i]
			p2 = target_points[i+1]
			if other_colonies:
				path = self._generate_path_waypoints(p1, p2, other_colonies)
				final_waypoints.extend(path)
			else:
				final_waypoints.append(p2)
		
		# Close the loop
		if other_colonies:
			path = self._generate_path_waypoints(target_points[-1], target_points[0], other_colonies)
			final_waypoints.extend(path)
		else:
			final_waypoints.append(target_points[0])
		
		fleet.waypoints = final_waypoints
		fleet.state = "Patrolling"
		self._mark_changed()

	def can_build_flanker_group(self) -> bool:
		"""Check if the colony can build a flanker group."""
		# Check if flanker type is unlocked
		if not self.can_build_fleet_type("Flanker"):
			return False
		
		# Check cooldown
		if time.time() - self.last_flanker_build_time < flanker_build_cooldown:
			return False
			
		# REQUIREMENT: Must have at least one oil pump to build fleets
		# This ensures they have established some infrastructure first
		if not self.colony.planet.oilPumps or len(self.colony.planet.oilPumps) < 1:
			return False
		
		# Check max fleet groups limit
		if self.colony.colonyLevel.value in colony_level_thresholds:
			max_groups = colony_level_thresholds[self.colony.colonyLevel.value].get("max_fleet_groups", 1)
			# Count current fleet groups (all types)
			if self.colony.colonyFleet:
				total_fleets = len([f for f in self.colony.colonyFleet if f.type in ["Flanker", "Fighter", "Bomber", "Scout"]])
				if total_fleets >= max_groups:
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
		
		# Calculate spawn position above the BASE
		base_pos = self._get_planet_base_position()
		planet_pos = self.colony.planet.position
		
		# Calculate outward normal from planet center to base
		dx = base_pos.x - planet_pos.x
		dy = base_pos.y - planet_pos.y
		dz = base_pos.z - planet_pos.z
		dist = math.sqrt(dx*dx + dy*dy + dz*dz)
		
		if dist > 0.001:
			nx, ny, nz = dx/dist, dy/dist, dz/dist
		else:
			nx, ny, nz = 0, 1, 0
            
		# Spawn fleets high above the base (e.g., 3 units altitude)
		spawn_altitude = 3.0
		fleet_spawn_pos = Vector3(
			x=base_pos.x + nx * spawn_altitude,
			y=base_pos.y + ny * spawn_altitude,
			z=base_pos.z + nz * spawn_altitude
		)
		
		# Initialize colonyFleet if needed
		if self.colony.colonyFleet is None:
			self.colony.colonyFleet = []
		
		# Create a single fleet entity that represents the flanker group
		# The frontend will handle rendering the formation based on count
		
		group_id = str(uuid.uuid4())[:8]
		
		# Get fleet stats from config
		fleet_stats = _CONFIG.get("fleet_stats", {}).get("Flanker", {})
		fleet_speed = fleet_stats.get("speed", 5.0)
		fleet_max_hp = fleet_stats.get("maxHP", 100.0)
		fleet_damage = fleet_stats.get("damage", 15.0)
		
		flanker_fleet = Fleet(
			id=f"flanker_{group_id}",
			type="Flanker",
			label=f"{self.colony.name} Flankers",
			count=flanker_group_size,  # Backend tracks count, frontend renders formation
			position=Vector3(
				x=fleet_spawn_pos.x,
				y=fleet_spawn_pos.y,
				z=fleet_spawn_pos.z
			),
			velocity=Vector3(x=0.0, y=0.0, z=0.0),
			state="Idle",
			tactic="Offensive",
			hpPool=fleet_max_hp * flanker_group_size,  # Total HP for the group
			maxHP=fleet_max_hp,  # HP per ship
			damage=fleet_damage,  # Damage per ship
			speed=fleet_speed,  # Movement speed
			waypoints=None,  # Start with None - will be set by behavior update
			homePosition=Vector3(
				x=fleet_spawn_pos.x,
				y=fleet_spawn_pos.y,
				z=fleet_spawn_pos.z
			)  # Remember spawn position for patrol
		)
		
		# Set initial patrol cooldown to allow immediate waypoint generation
		self._fleet_patrol_cooldowns[flanker_fleet.id] = 0
		
		self.colony.colonyFleet.append(flanker_fleet)
		
		# Update last build time
		self.last_flanker_build_time = time.time()
		
		# NEW: If there's an ongoing attack, immediately add this fleet to it
		if self.attack_target_colony_id:
			# Find the target colony
			for target_col in (self._get_all_colonies_cache() or []):
				if target_col.colony.id == self.attack_target_colony_id:
					self._add_fleet_to_attack(flanker_fleet, target_col)
					break
		
		self._mark_changed()
		
		# Log the build event
		self._add_action_event(f"built a Flanker group ({flanker_group_size} ships)", "build")
		
		return flanker_fleet

	def can_build_fighter_group(self) -> bool:
		"""Check if the colony can build a fighter group."""
		if not self.can_build_fleet_type("Fighter"):
			return False
		if time.time() - self.last_fighter_build_time < fighter_build_cooldown:
			return False
		if not self.colony.planet.oilPumps or len(self.colony.planet.oilPumps) < 1:
			return False

		# Check max fleet groups limit
		if self.colony.colonyLevel.value in colony_level_thresholds:
			max_groups = colony_level_thresholds[self.colony.colonyLevel.value].get("max_fleet_groups", 1)
			if self.colony.colonyFleet:
				total_fleets = len([f for f in self.colony.colonyFleet if f.type in ["Flanker", "Fighter", "Bomber", "Scout"]])
				if total_fleets >= max_groups:
					return False
		
		resources = self.colony.planet.planetNaturalResources
		if resources.steelStorage < fighter_steel_cost:
			return False
		if resources.oilStorage < fighter_oil_cost:
			return False
		
		return True

	def build_fighter_group(self) -> Optional[Fleet]:
		if not self.can_build_fighter_group():
			return None
		
		resources = self.colony.planet.planetNaturalResources
		resources.steelStorage -= fighter_steel_cost
		resources.oilStorage -= fighter_oil_cost
		
		base_pos = self._get_planet_base_position()
		planet_pos = self.colony.planet.position
		
		dx = base_pos.x - planet_pos.x
		dy = base_pos.y - planet_pos.y
		dz = base_pos.z - planet_pos.z
		dist = math.sqrt(dx*dx + dy*dy + dz*dz)
		
		if dist > 0.001:
			nx, ny, nz = dx/dist, dy/dist, dz/dist
		else:
			nx, ny, nz = 0, 1, 0
            
		spawn_altitude = 3.0
		fleet_spawn_pos = Vector3(
			x=base_pos.x + nx * spawn_altitude,
			y=base_pos.y + ny * spawn_altitude,
			z=base_pos.z + nz * spawn_altitude
		)
		
		if self.colony.colonyFleet is None:
			self.colony.colonyFleet = []
		
		group_id = str(uuid.uuid4())[:8]
		
		fleet_stats = _CONFIG.get("fleet_stats", {}).get("Fighter", {})
		fleet_speed = fleet_stats.get("speed", 6.0)
		fleet_max_hp = fleet_stats.get("maxHP", 80.0)
		fleet_damage = fleet_stats.get("damage", 10.0)
		
		fleet = Fleet(
			id=f"fighter_{group_id}",
			type="Fighter",
			label=f"{self.colony.name} Fighters",
			count=fighter_group_size,
			position=Vector3(x=fleet_spawn_pos.x, y=fleet_spawn_pos.y, z=fleet_spawn_pos.z),
			velocity=Vector3(x=0.0, y=0.0, z=0.0),
			state="Idle",
			tactic="Offensive",
			hpPool=fleet_max_hp * fighter_group_size,
			maxHP=fleet_max_hp,
			damage=fleet_damage,
			speed=fleet_speed,
			homePosition=Vector3(x=fleet_spawn_pos.x, y=fleet_spawn_pos.y, z=fleet_spawn_pos.z)
		)
		
		self._fleet_patrol_cooldowns[fleet.id] = 0
		self.colony.colonyFleet.append(fleet)
		self.last_fighter_build_time = time.time()
		
		if self.attack_target_colony_id:
			for target_col in (self._get_all_colonies_cache() or []):
				if target_col.colony.id == self.attack_target_colony_id:
					self._add_fleet_to_attack(fleet, target_col)
					break
		
		self._mark_changed()
		self._add_action_event(f"built a Fighter group ({fighter_group_size} ships)", "build")
		return fleet

	def can_build_bomber_group(self) -> bool:
		"""Check if the colony can build a bomber group."""
		if not self.can_build_fleet_type("Bomber"):
			return False
		if time.time() - self.last_bomber_build_time < bomber_build_cooldown:
			return False
		if not self.colony.planet.oilPumps or len(self.colony.planet.oilPumps) < 1:
			return False

		if self.colony.colonyLevel.value in colony_level_thresholds:
			max_groups = colony_level_thresholds[self.colony.colonyLevel.value].get("max_fleet_groups", 1)
			if self.colony.colonyFleet:
				total_fleets = len([f for f in self.colony.colonyFleet if f.type in ["Flanker", "Fighter", "Bomber", "Scout"]])
				if total_fleets >= max_groups:
					return False
		
		resources = self.colony.planet.planetNaturalResources
		if resources.steelStorage < bomber_steel_cost:
			return False
		if resources.oilStorage < bomber_oil_cost:
			return False
		
		return True

	def build_bomber_group(self) -> Optional[Fleet]:
		if not self.can_build_bomber_group():
			return None
		
		resources = self.colony.planet.planetNaturalResources
		resources.steelStorage -= bomber_steel_cost
		resources.oilStorage -= bomber_oil_cost
		
		base_pos = self._get_planet_base_position()
		planet_pos = self.colony.planet.position
		
		dx = base_pos.x - planet_pos.x
		dy = base_pos.y - planet_pos.y
		dz = base_pos.z - planet_pos.z
		dist = math.sqrt(dx*dx + dy*dy + dz*dz)
		
		if dist > 0.001:
			nx, ny, nz = dx/dist, dy/dist, dz/dist
		else:
			nx, ny, nz = 0, 1, 0
            
		spawn_altitude = 3.0
		fleet_spawn_pos = Vector3(
			x=base_pos.x + nx * spawn_altitude,
			y=base_pos.y + ny * spawn_altitude,
			z=base_pos.z + nz * spawn_altitude
		)
		
		if self.colony.colonyFleet is None:
			self.colony.colonyFleet = []
		
		group_id = str(uuid.uuid4())[:8]
		
		fleet_stats = _CONFIG.get("fleet_stats", {}).get("Bomber", {})
		fleet_speed = fleet_stats.get("speed", 4.0)
		fleet_max_hp = fleet_stats.get("maxHP", 150.0)
		fleet_damage = fleet_stats.get("damage", 30.0)
		
		fleet = Fleet(
			id=f"bomber_{group_id}",
			type="Bomber",
			label=f"{self.colony.name} Bombers",
			count=bomber_group_size,
			position=Vector3(x=fleet_spawn_pos.x, y=fleet_spawn_pos.y, z=fleet_spawn_pos.z),
			velocity=Vector3(x=0.0, y=0.0, z=0.0),
			state="Idle",
			tactic="Offensive",
			hpPool=fleet_max_hp * bomber_group_size,
			maxHP=fleet_max_hp,
			damage=fleet_damage,
			speed=fleet_speed,
			homePosition=Vector3(x=fleet_spawn_pos.x, y=fleet_spawn_pos.y, z=fleet_spawn_pos.z)
		)
		
		self._fleet_patrol_cooldowns[fleet.id] = 0
		self.colony.colonyFleet.append(fleet)
		self.last_bomber_build_time = time.time()
		
		if self.attack_target_colony_id:
			for target_col in (self._get_all_colonies_cache() or []):
				if target_col.colony.id == self.attack_target_colony_id:
					self._add_fleet_to_attack(fleet, target_col)
					break
		
		self._mark_changed()
		self._add_action_event(f"built a Bomber group ({bomber_group_size} ships)", "build")
		return fleet

	def can_build_scout_group(self) -> bool:
		"""Check if the colony can build a scout group."""
		if not self.can_build_fleet_type("Scout"):
			return False
		if time.time() - self.last_scout_build_time < scout_build_cooldown:
			return False
		if not self.colony.planet.oilPumps or len(self.colony.planet.oilPumps) < 1:
			return False

		if self.colony.colonyLevel.value in colony_level_thresholds:
			max_groups = colony_level_thresholds[self.colony.colonyLevel.value].get("max_fleet_groups", 1)
			if self.colony.colonyFleet:
				total_fleets = len([f for f in self.colony.colonyFleet if f.type in ["Flanker", "Fighter", "Bomber", "Scout"]])
				if total_fleets >= max_groups:
					return False
		
		resources = self.colony.planet.planetNaturalResources
		if resources.steelStorage < scout_steel_cost:
			return False
		if resources.oilStorage < scout_oil_cost:
			return False
		
		return True

	def build_scout_group(self) -> Optional[Fleet]:
		if not self.can_build_scout_group():
			return None
		
		resources = self.colony.planet.planetNaturalResources
		resources.steelStorage -= scout_steel_cost
		resources.oilStorage -= scout_oil_cost
		
		base_pos = self._get_planet_base_position()
		planet_pos = self.colony.planet.position
		
		dx = base_pos.x - planet_pos.x
		dy = base_pos.y - planet_pos.y
		dz = base_pos.z - planet_pos.z
		dist = math.sqrt(dx*dx + dy*dy + dz*dz)
		
		if dist > 0.001:
			nx, ny, nz = dx/dist, dy/dist, dz/dist
		else:
			nx, ny, nz = 0, 1, 0
            
		spawn_altitude = 3.0
		fleet_spawn_pos = Vector3(
			x=base_pos.x + nx * spawn_altitude,
			y=base_pos.y + ny * spawn_altitude,
			z=base_pos.z + nz * spawn_altitude
		)
		
		if self.colony.colonyFleet is None:
			self.colony.colonyFleet = []
		
		group_id = str(uuid.uuid4())[:8]
		
		fleet_stats = _CONFIG.get("fleet_stats", {}).get("Scout", {})
		fleet_speed = fleet_stats.get("speed", 8.0)
		fleet_max_hp = fleet_stats.get("maxHP", 50.0)
		fleet_damage = fleet_stats.get("damage", 5.0)
		
		fleet = Fleet(
			id=f"scout_{group_id}",
			type="Scout",
			label=f"{self.colony.name} Scouts",
			count=scout_group_size,
			position=Vector3(x=fleet_spawn_pos.x, y=fleet_spawn_pos.y, z=fleet_spawn_pos.z),
			velocity=Vector3(x=0.0, y=0.0, z=0.0),
			state="Idle",
			tactic="Defensive",
			hpPool=fleet_max_hp * scout_group_size,
			maxHP=fleet_max_hp,
			damage=fleet_damage,
			speed=fleet_speed,
			homePosition=Vector3(x=fleet_spawn_pos.x, y=fleet_spawn_pos.y, z=fleet_spawn_pos.z)
		)
		
		self._fleet_patrol_cooldowns[fleet.id] = 0
		self.colony.colonyFleet.append(fleet)
		self.last_scout_build_time = time.time()
		
		if self.attack_target_colony_id:
			for target_col in (self._get_all_colonies_cache() or []):
				if target_col.colony.id == self.attack_target_colony_id:
					self._add_fleet_to_attack(fleet, target_col)
					break
		
		self._mark_changed()
		self._add_action_event(f"built a Scout group ({scout_group_size} ships)", "build")
		return fleet

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

		# Assign random trait if not provided
		if 'trait' not in _payload or not _payload.get('trait'):
			traits = [ColonyTrait.Pacifist, ColonyTrait.Aggressive, ColonyTrait.Defensive, ColonyTrait.Economic]
			_payload['trait'] = random.choice(traits).value

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
					"oilStorage": initial_oil_storage,
					"steelStorage": initial_steel_storage,
					"waterStorage": initial_water_storage,
				},
			}
			_payload['planet'] = planet

		colony_model = ColonyModel(**_payload)
		return cls(colony_model)

	def _get_collision_free_direction(self, start: Vector3, end: Vector3, all_colonies: List['Colony']) -> Vector3:
		"""Calculate a direction towards end that avoids planet collisions (Go Around behavior)."""
		dir_vec_x = end.x - start.x
		dir_vec_y = end.y - start.y
		dir_vec_z = end.z - start.z
		total_dist = math.sqrt(dir_vec_x**2 + dir_vec_y**2 + dir_vec_z**2)
		
		if total_dist < 0.001: 
			return Vector3(x=0.0, y=0.0, z=0.0)
		
		# Normalized original direction
		ndx, ndy, ndz = dir_vec_x / total_dist, dir_vec_y / total_dist, dir_vec_z / total_dist
		
		intersecting_planet = None
		closest_impact_dist = total_dist
		
		# Check all planets for obstruction
		for c in all_colonies:
			p_pos = c.colony.planet.position
			# Use the same radius formula as the hard-clip check + a buffer for smooth avoidance
			# Hard clip is: scale * rad * 1.1 + 3.0
			base_safe_radius = c.colony.planet.scale * planet_model_radius * 1.1 + 3.0
			p_radius = base_safe_radius * 1.2 # Give it 20% more clearance for steering
			
			# Vector to planet center
			ox = p_pos.x - start.x
			oy = p_pos.y - start.y
			oz = p_pos.z - start.z
			
			# Project planet center onto line of flight
			# t = Dot(SphereCenter - Start, Dir)
			t = ox * ndx + oy * ndy + oz * ndz
			
			# Planet is behind us (and we are outside) or too far ahead
			# Note: If we are INSIDE the radius (t < 0 but close), we might need to escape. 
			# But "push out" logic handles escape. This handles "Navigation".
			if t < 0 or t > total_dist:
				continue
				
			# Closest point on line to sphere center
			cpx = start.x + ndx * t
			cpy = start.y + ndy * t
			cpz = start.z + ndz * t
			
			# Distance from closest point to sphere center
			dist_sq = (cpx - p_pos.x)**2 + (cpy - p_pos.y)**2 + (cpz - p_pos.z)**2
			
			if dist_sq < p_radius * p_radius:
				# Collision detected
				if t < closest_impact_dist:
					closest_impact_dist = t
					intersecting_planet = (c, t, dist_sq)

		if not intersecting_planet:
			return Vector3(x=ndx, y=ndy, z=ndz)

		# Handle Intersection -> Calculate Detour
		c, t, dist_sq = intersecting_planet
		p_pos = c.colony.planet.position
		
		# Re-calculate specific radius for the intersected planet
		base_safe_radius = c.colony.planet.scale * planet_model_radius * 1.1 + 3.0
		p_radius = base_safe_radius * 1.2
		
		# We want a detour point at the "Horizon" of the safety sphere.
		# Construct closest point on the ray
		cpx = start.x + ndx * t
		cpy = start.y + ndy * t
		cpz = start.z + ndz * t
		
		# Vector from Planet to that Closest Point (Radial vector)
		rad_x = cpx - p_pos.x
		rad_y = cpy - p_pos.y
		rad_z = cpz - p_pos.z
		rad_len = math.sqrt(rad_x**2 + rad_y**2 + rad_z**2)
		
		if rad_len < 0.001:
			# Direct hit through center. Pick arbitrary up.
			rad_x, rad_y, rad_z = 0.0, 1.0, 0.0
			rad_len = 1.0
		
		# Detour point: Move the closest collision point OUTWARD to the safety radius
		# This effectively aims the ship at the "edge" of the planet interference zone
		buffer = 1.2
		detour_x = p_pos.x + (rad_x / rad_len) * (p_radius * buffer)
		detour_y = p_pos.y + (rad_y / rad_len) * (p_radius * buffer)
		detour_z = p_pos.z + (rad_z / rad_len) * (p_radius * buffer)
		
		# New direction: Start -> Detour
		new_dir_x = detour_x - start.x
		new_dir_y = detour_y - start.y
		new_dir_z = detour_z - start.z
		new_len = math.sqrt(new_dir_x**2 + new_dir_y**2 + new_dir_z**2)
		
		if new_len > 0.001:
			return Vector3(x=new_dir_x/new_len, y=new_dir_y/new_len, z=new_dir_z/new_len)
		
		return Vector3(x=ndx, y=ndy, z=ndz)

	def _find_target(self, fleet: Fleet, all_colonies: List['Colony']):
		"""Find a suitable target (Enemy Colony Base or Fleet)."""
		potential_targets = []
		my_owner = self.colony.owner_id
		
		for other in all_colonies:
			if other.colony.id == self.colony.id: 
				continue
			other_owner = other.colony.owner_id if other.colony.owner_id else other.colony.id
			if other_owner == my_owner:
				continue

			# Target 1: The Main Base
			base_pos = other._get_planet_base_position()
			dist = self._distance_v3(fleet.position, base_pos)
			potential_targets.append((dist, other.colony.id, base_pos, "Base"))

			# Target 2: Fleets
			if other.colony.colonyFleet:
				for f in other.colony.colonyFleet:
					dist_f = self._distance_v3(fleet.position, f.position)
					potential_targets.append((dist_f, f.id, f.position, "Fleet"))

		if not potential_targets:
			return None
		
		potential_targets.sort(key=lambda x: x[0])
		_, target_id, target_pos, target_type = potential_targets[0]
		return target_id, target_pos, target_type

	def _scan_for_enemies(self, fleet: Fleet, all_colonies: List['Colony'], scan_radius: Optional[float] = None):
		"""Scan for nearby enemy fleets within detection radius.
		
		Args:
			fleet: The fleet doing the scanning
			all_colonies: All colonies in the game
			scan_radius: Optional custom scan radius (defaults to config value)
			
		Returns:
			Tuple of (fleet_id, position, type, distance, owner_colony) or None
		"""
		if scan_radius is None:
			scan_radius = fleet_awareness_radius
		
		# Ensure we have a valid radius
		actual_radius: float = float(scan_radius) if scan_radius is not None else 35.0
			
		my_owner = self.colony.owner_id
		
		closest_dist: float = actual_radius
		closest = None
		
		# Check fleets from all enemy colonies
		for other in all_colonies:
			if other.colony.id == self.colony.id:
				continue
				
			other_owner = other.colony.owner_id if other.colony.owner_id else other.colony.id
			if other_owner == my_owner:
				continue
			
			if other.colony.colonyFleet:
				for f in other.colony.colonyFleet:
					dist = self._distance_v3(fleet.position, f.position)
					if dist < closest_dist:
						closest_dist = dist
						closest = (f.id, f.position, "Fleet", dist, other)
		
		return closest

	def _update_fleet_awareness(self, fleet: Fleet, all_colonies: List['Colony']):
		"""Update fleet awareness and handle automatic engagement of nearby enemies."""
		# Pacifist fleets don't engage
		if self.colony.trait == ColonyTrait.Pacifist.value:
			return
		
		# Scan for nearby enemies
		nearby_enemy = self._scan_for_enemies(fleet, all_colonies)
		if not nearby_enemy:
			return
		
		enemy_id, enemy_pos, enemy_type, distance, enemy_colony = nearby_enemy
		
		# Decision logic based on fleet state and distance
		should_engage = False
		
		if fleet.state == "Idle":
			# Idle fleets always engage nearby enemies
			should_engage = True
			
		elif fleet.state == "Patrolling":
			# Patrolling fleets engage if enemy is close enough (priority threat)
			if distance < fleet_engagement_priority_distance:
				should_engage = True
			
		elif fleet.state == "Moving":
			# Moving fleets engage if:
			# 1. Enemy is very close (immediate threat)
			# 2. OR they're not on a coordinated attack mission
			if distance < fleet_engagement_priority_distance:
				should_engage = True
			elif not (fleet.target and fleet.target.id == self.attack_target_colony_id):
				# Not on coordinated attack, can intercept
				if distance < fleet_awareness_radius * 0.7:  # Within 70% of awareness radius
					should_engage = True
		
		# Already attacking someone else - only switch if this enemy is much closer
		if fleet.state == "Attacking" and fleet.target:
			# Don't switch targets unless this is significantly closer
			return
		
		if should_engage:
			# Check if we're already targeting this enemy
			if fleet.target and fleet.target.id == enemy_id:
				return
			
			# Engage the enemy
			self._order_attack_move(fleet, enemy_id, enemy_pos, all_colonies)
			self._mark_changed()

	def _get_detour_point(self, start: Vector3, end: Vector3, center: Vector3, radius: float) -> Optional[Vector3]:
		"""Calculate a detour point if the segment intersects the sphere."""
		# Vector from Start to End
		ab_x = end.x - start.x
		ab_y = end.y - start.y
		ab_z = end.z - start.z
		ab_len_sq = ab_x*ab_x + ab_y*ab_y + ab_z*ab_z
		
		if ab_len_sq == 0:
			return None
			
		# Vector from Start to Center
		ac_x = center.x - start.x
		ac_y = center.y - start.y
		ac_z = center.z - start.z
		
		# Project C onto AB to find closest point P parameter t
		t = (ac_x*ab_x + ac_y*ab_y + ac_z*ab_z) / ab_len_sq
		
		# Clamp t to segment [0, 1]
		closest_t = max(0.0, min(1.0, t))
		
		# P = Start + t * AB
		px = start.x + closest_t * ab_x
		py = start.y + closest_t * ab_y
		pz = start.z + closest_t * ab_z
		
		# Vector from Center to P
		cp_x = px - center.x
		cp_y = py - center.y
		cp_z = pz - center.z
		dist_sq = cp_x*cp_x + cp_y*cp_y + cp_z*cp_z
		
		if dist_sq >= radius*radius:
			return None # No intersection
			
		# Intersection!
		# Calculate detour direction: Normalize CP (outward from center)
		dist = math.sqrt(dist_sq)
		if dist < 0.001:
			# Passes through center? Pick arbitrary "Up" or orthogonal
			if abs(ab_z) > abs(ab_x) and abs(ab_z) > abs(ab_y):
				nx, ny, nz = 0, 1, 0
			else:
				nx, ny, nz = 0, 0, 1
		else:
			nx, ny, nz = cp_x/dist, cp_y/dist, cp_z/dist
			
		# Detour point = Center + Normal * (Radius + Margin)
		margin = 8.0 
		safe_dist = radius + margin
		
		return Vector3(
			x = center.x + nx * safe_dist,
			y = center.y + ny * safe_dist,
			z = center.z + nz * safe_dist
		)

	def _generate_path_waypoints(self, start: Vector3, end: Vector3, all_colonies: List['Colony'], depth: int = 0) -> List[Vector3]:
		"""Recursively generate waypoints to avoid planets."""
		if depth > 2: # Limit recursion
			return [end]
		
		if not all_colonies:
			return [end]
			
		best_detour = None
		closest_sq_dist = float('inf')
		
		for col in all_colonies:
			# Planet stats
			p_pos = col.colony.planet.position
			p_scale = col.colony.planet.scale
			p_radius = p_scale * planet_model_radius * 1.1 + 3.0
			
			detour = self._get_detour_point(start, end, p_pos, p_radius)
			if detour:
				# Prioritize the obstacle closest to the start
				d_sq = (p_pos.x-start.x)**2 + (p_pos.y-start.y)**2 + (p_pos.z-start.z)**2
				
				if d_sq < closest_sq_dist:
					closest_sq_dist = d_sq
					best_detour = detour
		
		if not best_detour:
			return [end]
			
		# Determine path segments avoiding the best_detour
		path1 = self._generate_path_waypoints(start, best_detour, all_colonies, depth + 1)
		path2 = self._generate_path_waypoints(best_detour, end, all_colonies, depth + 1)
		
		return path1 + path2

	def _order_attack_move(self, fleet: Fleet, target_id: str, target_pos: Vector3, all_colonies: List['Colony'], target_type: str = "Base"):
		"""Order fleet to move to a firing position near target."""
		
		final_pos = None
		
		# Strategy 1: For Base targets, aim for a position "Above" the base relative to planet center
		# This guarantees Line of Sight and prevents trying to path through the planet
		if target_type == "Base":
			# Find the owner colony to get planet center
			target_colony = next((c for c in all_colonies if c.colony.id == target_id), None)
			if target_colony:
				planet_pos = target_colony.colony.planet.position
				
				# Vector from Planet Center to Base (The "Up" vector)
				nx = target_pos.x - planet_pos.x
				ny = target_pos.y - planet_pos.y
				nz = target_pos.z - planet_pos.z
				n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
				
				if n_len > 0.001:
					# Normalize
					nx, ny, nz = nx/n_len, ny/n_len, nz/n_len
					
					# Attack position = Base + Normal * Range
					attack_range = 12.0
					final_pos = Vector3(
						x = target_pos.x + nx * attack_range,
						y = target_pos.y + ny * attack_range,
						z = target_pos.z + nz * attack_range
					)

		# Strategy 2: Default / Fallback (For fleets or if base lookup failed)
		# Aim for a point along the line between Fleet and Target
		if not final_pos:
			dx = fleet.position.x - target_pos.x
			dy = fleet.position.y - target_pos.y
			dz = fleet.position.z - target_pos.z
			dist = math.sqrt(dx*dx + dy*dy + dz*dz)
			
			attack_range = 12.0
			
			if dist == 0:
				direction = Vector3(x=1, y=0, z=0)
			else:
				direction = Vector3(x=dx/dist, y=dy/dist, z=dz/dist)
				
			final_x = target_pos.x + direction.x * attack_range
			final_y = target_pos.y + direction.y * attack_range
			final_z = target_pos.z + direction.z * attack_range
			
			final_pos = Vector3(x=final_x, y=final_y, z=final_z)
		
		# Generate a safe path of waypoints to the determined firing position
		waypoints = self._generate_path_waypoints(fleet.position, final_pos, all_colonies)
		
		fleet.waypoints = waypoints
		# Use elevated target position for Base targets so ships aim at the
		# visual center of the settlement, not the ground beneath it
		if target_type == "Base":
			target_colony = next((c for c in all_colonies if c.colony.id == target_id), None)
			aim_pos = target_colony._get_base_target_position() if target_colony else target_pos
		else:
			aim_pos = target_pos
		fleet.target = FleetTarget(id=target_id, position=aim_pos)
		fleet.state = "Moving"
		self._mark_changed()

	def _calculate_parking_spots(self, target_colony: 'Colony', num_spots: int) -> List[Vector3]:
		"""Calculate parking spot positions around a target colony for attacking fleets.
		
		Spots are arranged in a sphere around the target colony's base position.
		"""
		target_base_pos = target_colony._get_planet_base_position()
		target_planet_pos = target_colony.colony.planet.position
		
		# Calculate outward normal from planet center to base
		nx = target_base_pos.x - target_planet_pos.x
		ny = target_base_pos.y - target_planet_pos.y
		nz = target_base_pos.z - target_planet_pos.z
		n_len = math.sqrt(nx*nx + ny*ny + nz*nz)
		
		if n_len > 0.001:
			nx, ny, nz = nx/n_len, ny/n_len, nz/n_len
		else:
			nx, ny, nz = 0, 1, 0
		
		parking_spots = []
		
		# Create a coordinate system with the normal as "up"
		# Find a perpendicular "right" vector
		if abs(ny) > 0.9:
			# Normal is close to Y axis, use X as reference
			rx, ry, rz = 1, 0, 0
		else:
			# Normal is not Y, use Y as reference
			rx, ry, rz = 0, 1, 0
		
		# Right = Cross(Reference, Normal)
		t_rx = ry*nz - rz*ny
		t_ry = rz*nx - rx*nz
		t_rz = rx*ny - ry*nx
		
		# Normalize Right
		t_len = math.sqrt(t_rx*t_rx + t_ry*t_ry + t_rz*t_rz)
		if t_len > 0.001:
			t_rx, t_ry, t_rz = t_rx/t_len, t_ry/t_len, t_rz/t_len
		else:
			t_rx, t_ry, t_rz = 1, 0, 0
		
		# Forward = Cross(Normal, Right)
		fx = ny*t_rz - nz*t_ry
		fy = nz*t_rx - nx*t_rz
		fz = nx*t_ry - ny*t_rx
		
		# Normalize Forward
		f_len = math.sqrt(fx*fx + fy*fy + fz*fz)
		if f_len > 0.001:
			fx, fy, fz = fx/f_len, fy/f_len, fz/f_len
		
		# Generate spots in a spherical pattern around the base
		# Use golden spiral or simple angular distribution
		for i in range(num_spots):
			# Use spherical coordinates with some randomness
			theta = (i * 2 * math.pi / num_spots) + random.uniform(-0.3, 0.3)  # Horizontal angle
			phi = random.uniform(math.pi/12, math.pi/5)  # Vertical angle from normal (15-36 degrees)
			
			# Radial distance with some spread
			radius = attack_parking_spot_distance + random.uniform(-attack_parking_spot_spread, attack_parking_spot_spread)
			
			# Convert spherical to Cartesian in local coordinate system
			# x = radius * sin(phi) * cos(theta)
			# y = radius * sin(phi) * sin(theta)  
			# z = radius * cos(phi)
			
			local_x = radius * math.sin(phi) * math.cos(theta)
			local_y = radius * math.sin(phi) * math.sin(theta)
			local_z = radius * math.cos(phi)
			
			# Transform to world space using our coordinate system
			# Position = Base + local_x*Right + local_y*Forward + local_z*Normal
			spot_x = target_base_pos.x + local_x*t_rx + local_y*fx + local_z*nx
			spot_y = target_base_pos.y + local_x*t_ry + local_y*fy + local_z*ny
			spot_z = target_base_pos.z + local_x*t_rz + local_y*fz + local_z*nz
			
			parking_spots.append(Vector3(x=spot_x, y=spot_y, z=spot_z))
		
		return parking_spots

	def _assign_parking_spots_to_fleets(self, fleets: List[Fleet], target_colony: 'Colony'):
		"""Assign parking spots to fleets for coordinated attack."""
		if not fleets:
			return
		
		# Calculate parking spots
		parking_spots = self._calculate_parking_spots(target_colony, len(fleets))
		
		# Clear old assignments
		self._fleet_parking_spots = {}
		
		# Assign spots to fleets (closest fleet gets closest spot for efficiency)
		remaining_fleets = fleets.copy()
		remaining_spots = parking_spots.copy()
		
		while remaining_fleets and remaining_spots:
			# Find the fleet-spot pair with minimum distance
			best_fleet = None
			best_spot = None
			min_dist = float('inf')
			
			for fleet in remaining_fleets:
				for spot in remaining_spots:
					dist = self._distance_v3(fleet.position, spot)
					if dist < min_dist:
						min_dist = dist
						best_fleet = fleet
						best_spot = spot
			
			if best_fleet and best_spot:
				self._fleet_parking_spots[best_fleet.id] = best_spot
				remaining_fleets.remove(best_fleet)
				remaining_spots.remove(best_spot)

	def _should_initiate_attack(self, all_colonies: List['Colony']) -> bool:
		"""Decide if colony should initiate an attack based on trait, resources, and cooldown."""
		current_time = time.time()
		
		# Check cooldown
		if current_time - self.attack_decision_time < self.attack_decision_cooldown:
			return False
		
		# Pacifist colonies never initiate attacks
		if self.colony.trait == ColonyTrait.Pacifist.value:
			return False
		
		# Must have at least one fleet
		if not self.colony.colonyFleet or len(self.colony.colonyFleet) == 0:
			return False
		
		# Don't initiate new attack if already attacking
		if self.attack_target_colony_id is not None:
			return False
		
		# Check if any enemy colonies exist
		my_owner = self.colony.owner_id
		has_enemies = False
		for other in all_colonies:
			if other.colony.id == self.colony.id:
				continue
			other_owner = other.colony.owner_id if other.colony.owner_id else other.colony.id
			if other_owner != my_owner:
				has_enemies = True
				break
		
		if not has_enemies:
			return False
		
		# Trait-based decision
		if self.colony.trait == ColonyTrait.Aggressive.value:
			# Aggressive colonies attack frequently
			return random.random() < 0.7
		elif self.colony.trait == ColonyTrait.Defensive.value:
			# Defensive colonies attack less frequently
			return random.random() < 0.3
		elif self.colony.trait == ColonyTrait.Economic.value:
			# Economic colonies rarely attack
			return random.random() < 0.1
		
		return False

	def _select_attack_target(self, all_colonies: List['Colony']) -> Optional['Colony']:
		"""Select an enemy colony to attack."""
		my_owner = self.colony.owner_id
		my_base_pos = self._get_planet_base_position()
		
		potential_targets = []
		
		for other in all_colonies:
			if other.colony.id == self.colony.id:
				continue
			other_owner = other.colony.owner_id if other.colony.owner_id else other.colony.id
			if other_owner == my_owner:
				continue
			
			# Calculate distance to target
			other_base_pos = other._get_planet_base_position()
			dist = self._distance_v3(my_base_pos, other_base_pos)
			
			potential_targets.append((dist, other))
		
		if not potential_targets:
			return None
		
		# Sort by distance and pick closest (or could use other strategies)
		potential_targets.sort(key=lambda x: x[0])
		
		# Aggressive colonies might prefer weaker targets
		if self.colony.trait == ColonyTrait.Aggressive.value:
			# Pick from closest 3 based on weakness
			candidates = potential_targets[:min(3, len(potential_targets))]
			# Sort by residents (weaker = fewer residents)
			candidates.sort(key=lambda x: x[1].colony.residents)
			return candidates[0][1] if candidates else None
		
		# Default: attack closest
		return potential_targets[0][1]

	def _order_colony_wide_attack(self, target_colony: 'Colony', all_colonies: List['Colony']):
		"""Order all available fleets to attack the target colony in coordinated fashion."""
		if not self.colony.colonyFleet:
			return
		
		# Filter available fleets (not already attacking this target)
		available_fleets = [
			f for f in self.colony.colonyFleet 
			if f.state in ["Idle", "Patrolling"] and 
			   (not f.target or f.target.id != target_colony.colony.id)
		]
		
		if not available_fleets:
			return
		
		# Set colony-level attack target
		self.attack_target_colony_id = target_colony.colony.id
		self.attack_decision_time = time.time()
		
		# Assign parking spots to ALL fleets (including already attacking ones)
		all_attacking_fleets = [
			f for f in self.colony.colonyFleet
			if f.target and f.target.id == target_colony.colony.id
		] + available_fleets
		
		self._assign_parking_spots_to_fleets(all_attacking_fleets, target_colony)
		
		# Get target information
		target_base_pos = target_colony._get_planet_base_position()
		target_id = target_colony.colony.id
		
		# Order each NEW fleet to move to its assigned parking spot
		for fleet in available_fleets:
			self._add_fleet_to_attack(fleet, target_colony)
		
		self._mark_changed()
		self._add_action_event(f"Ordered attack on {target_colony.colony.name}", "military")

	def _add_fleet_to_attack(self, fleet: Fleet, target_colony: 'Colony'):
		"""Add a single fleet to the ongoing attack on target_colony."""
		# Get or assign parking spot
		if fleet.id not in self._fleet_parking_spots:
			# Calculate a new parking spot for this fleet
			new_spots = self._calculate_parking_spots(target_colony, 1)
			if new_spots:
				self._fleet_parking_spots[fleet.id] = new_spots[0]
		
		parking_spot = self._fleet_parking_spots.get(fleet.id)
		if not parking_spot:
			return
		
		# Get target information — use elevated position so ships aim at the
		# visual center of the settlement, not the ground
		target_attack_pos = target_colony._get_base_target_position()
		target_id = target_colony.colony.id
		
		# Generate path to parking spot
		all_colonies = self._all_colonies_cache or []
		waypoints = self._generate_path_waypoints(fleet.position, parking_spot, all_colonies)
		
		fleet.waypoints = waypoints
		fleet.target = FleetTarget(id=target_id, position=target_attack_pos)
		fleet.state = "Moving"
		self._mark_changed()

	def _reinforce_attack(self, target_colony: 'Colony', all_colonies: List['Colony']):
		"""Add any newly available fleets to an ongoing attack."""
		if not self.colony.colonyFleet:
			return
		
		# Find fleets that are idle/patrolling and not yet assigned to this attack
		new_reinforcements = [
			f for f in self.colony.colonyFleet
			if f.state in ["Idle", "Patrolling"] and
			   (not f.target or f.target.id != self.attack_target_colony_id)
		]
		
		if not new_reinforcements:
			return
		
		# Add each reinforcement to the attack
		for fleet in new_reinforcements:
			self._add_fleet_to_attack(fleet, target_colony)

	def _get_all_colonies_cache(self) -> Optional[List['Colony']]:
		"""Get cached list of all colonies (for use in spawning callbacks)."""
		return self._all_colonies_cache

	def update_combat(self, delta_time: float, all_colonies: List['Colony']):
		"""Handle combat logic for fleets and base."""
		# 1. Fleets
		# Create a copy of the fleet list to avoid modification-during-iteration issues
		if self.colony.colonyFleet:
			# Make a shallow copy of the list (not the fleet objects)
			fleets_to_process = list(self.colony.colonyFleet)
			for fleet in fleets_to_process:
				# Verify fleet still exists (might have been removed in previous iteration)
				if fleet not in self.colony.colonyFleet:
					continue
					
				if fleet.isAttacking and fleet.target and fleet.target.id:
					self._resolve_fleet_combat(fleet, delta_time, all_colonies)

		# 2. Base Defense (all levels can defend, with varying strength)
		self.colony.is_fighting = False
		self.colony.defense_target_id = None
		self.colony.defense_target_pos = None
		
		try:
			COLONY_LEVEL_ORDER.index(self.colony.colonyLevel)
			self._resolve_base_defense(delta_time, all_colonies)
		except ValueError:
			pass

	def _resolve_fleet_combat(self, fleet: Fleet, delta_time: float, all_colonies: List['Colony']):
		"""Process combat for a single fleet."""
		if not fleet.target or not fleet.target.id:
			return

		target_id = fleet.target.id
		target_colony = None
		target_obj: Union[ColonyModel, Fleet, None] = None
		target_type = "Unknown"
		target_pos: Optional[Vector3] = None
		
		for c in all_colonies:
			if c.colony.id == target_id:
				target_colony = c
				target_obj = c.colony
				target_type = "Base"
				target_pos = c._get_planet_base_position()
				break
			if c.colony.colonyFleet:
				for f in c.colony.colonyFleet:
					if f.id == target_id:
						target_colony = c
						target_obj = f
						target_type = "Fleet"
						target_pos = f.position
						break
			if target_obj: break
		
		if not target_obj or not target_colony or not target_pos:
			fleet.isAttacking = False
			fleet.target = None
			fleet.state = "Idle"
			self._mark_changed()
			return

		# Use elevated target position for Base targets so ships aim at the
		# visual center of the settlement, not the ground beneath it
		if target_type == "Base":
			fleet.target.position = target_colony._get_base_target_position()
		else:
			fleet.target.position = target_pos

		dist = self._distance_v3(fleet.position, target_pos)
		if dist > 30.0:
			fleet.isAttacking = False
			fleet.state = "Idle"
			self._mark_changed()
			return
		
		if not self._has_line_of_sight(fleet.position, target_pos, all_colonies):
			return

		# New Combat Logic: Synchronized States & Warmup
		if target_type == "Fleet":
			fleet_obj = cast(Fleet, target_obj)
			
			# If target is not yet engaging, force it to engage
			# But if it's already Attacking someone else (target.isAttacking == True), we don't interrupt?
			# User said: "Once a fleet is bound to attack another fleet, both will go into an 'attacking state'."
			# "Keep in mind that two fleets can attack one fleet" - so 2 vs 1. 
			# The single fleet can only be in one state. If it's already fighting someone, it stays fighting.
			
			# Force target to stay put and fight if potential victim
			if fleet_obj.state != "Attacking":
				fleet_obj.state = "Attacking"
				fleet_obj.isAttacking = True
				fleet_obj.velocity = Vector3(x=0.0, y=0.0, z=0.0)
				fleet_obj.waypoints = [] # Stop moving
				fleet_obj.combatWarmup = 2.0 # Force warmup on defender too
				# Should we set defender's target to us?
				# If defender has no target, yes.
				if not fleet_obj.target or not fleet_obj.target.id:
					fleet_obj.target = FleetTarget(id=fleet.id, position=fleet.position)
				
				target_colony._mark_changed()

		# Handle Warmup
		if fleet.combatWarmup > 0:
			fleet.combatWarmup -= delta_time
			# self._mark_changed() # Spammy if we update every tick just for timer?
			# Maybe only sync it occasionally or let client infer?
			# Code currently syncs all changes.
			return

		dps = fleet.damage if fleet.damage is not None else 10.0
		damage = dps * delta_time
		
		if target_type == "Fleet":
			fleet_obj = cast(Fleet, target_obj)
			current_hp = float(fleet_obj.hpPool) if fleet_obj.hpPool is not None else 100.0
			fleet_obj.hpPool = current_hp - damage
			if fleet_obj.hpPool <= 0:
				# Log fleet destruction for debugging
				print(f"Fleet {fleet_obj.id} destroyed. Target colony {target_colony.colony.name} had {len(target_colony.colony.colonyFleet) if target_colony.colony.colonyFleet else 0} fleets.")
				
				target_colony.remove_fleet(fleet_obj.id)
				target_colony._add_action_event("Fleet destroyed!", "combat")
				
				# Verify removal
				remaining_fleets = len(target_colony.colony.colonyFleet) if target_colony.colony.colonyFleet else 0
				print(f"After removal, target colony has {remaining_fleets} fleets.")
				
				fleet.isAttacking = False
				fleet.target = None
				fleet.state = "Idle"
				self._mark_changed()
		elif target_type == "Base":
			base_obj = cast(ColonyModel, target_obj)
			current_hp = float(base_obj.hp) if base_obj.hp is not None else base_obj.max_hp
			base_obj.hp = current_hp - damage
			
			if base_obj.hp <= 0:
				self._take_over_colony(target_colony)
				fleet.isAttacking = False
				fleet.target = None
				fleet.state = "Idle"
				self._mark_changed()

	def _take_over_colony(self, victim: 'Colony'):
		"""Handle taking over a defeated colony."""
		victim_name = victim.colony.name  # Store original name for action event
		victim.colony.owner_id = self.colony.owner_id
		victim.colony.hp = victim.colony.max_hp
		victim.colony.color = self.colony.color
		victim.colony.name = self.colony.name  # Update name to match conqueror
		victim.colony.colonyFleet = []
		
		victim._mark_changed()
		victim._add_action_event(f"Conquered by {self.colony.name}!", "defeat")
		self._add_action_event(f"Conquered {victim_name}!", "victory")

	def _resolve_base_defense(self, delta_time: float, all_colonies: List['Colony']):
		"""Base defense logic: Shoot closest enemy."""
		my_base_pos = self._get_planet_base_position()
		range_limit = 30.0
		
		closest_enemy = None
		closest_colony = None
		min_dist = range_limit
		
		for other in all_colonies:
			owner = other.colony.owner_id if other.colony.owner_id else other.colony.id
			if owner == self.colony.owner_id: continue
			
			if other.colony.colonyFleet:
				for f in other.colony.colonyFleet:
					# Rule: Only fire at fleets that are actively attacking THIS colony (Base)
					# This prevents premature shooting while the fleet is moving to position
					if not (f.isAttacking and f.target and f.target.id == self.colony.id):
						continue

					d = self._distance_v3(my_base_pos, f.position)
					if d < min_dist:
						if self._has_line_of_sight(my_base_pos, f.position, all_colonies):
							min_dist = d
							closest_enemy = f
							closest_colony = other
		
		if closest_enemy and closest_colony:
			# Mark as fighting for frontend animation
			self.colony.is_fighting = True
			self.colony.defense_target_id = closest_enemy.id
			self.colony.defense_target_pos = closest_enemy.position
			self._mark_changed()

			current_hp = float(closest_enemy.hpPool) if closest_enemy.hpPool is not None else 100.0
			# Per-level defense DPS from config
			level_key = self.colony.colonyLevel.value
			defense_dps = colony_defense_stats.get(level_key, {}).get("defense_dps", 5.0)
			closest_enemy.hpPool = current_hp - (defense_dps * delta_time)
			if closest_enemy.hpPool <= 0:
				# Log for debugging
				print(f"Base defense destroyed fleet {closest_enemy.id}. Colony {closest_colony.colony.name} had {len(closest_colony.colony.colonyFleet) if closest_colony.colony.colonyFleet else 0} fleets.")
				
				closest_colony.remove_fleet(closest_enemy.id)
				
				# Verify removal
				remaining_fleets = len(closest_colony.colony.colonyFleet) if closest_colony.colony.colonyFleet else 0
				print(f"After base defense removal, colony has {remaining_fleets} fleets.")
				
				self.colony.is_fighting = False
				self.colony.defense_target_id = None
				self.colony.defense_target_pos = None
				self._mark_changed()

	def _has_line_of_sight(self, p1: Vector3, p2: Vector3, all_colonies: List['Colony']) -> bool:
		dx = p2.x - p1.x
		dy = p2.y - p1.y
		dz = p2.z - p1.z
		dist = math.sqrt(dx*dx + dy*dy + dz*dz)
		if dist < 0.001: return True
		
		dir_x = dx/dist
		dir_y = dy/dist
		dir_z = dz/dist
		
		for c in all_colonies:
			center = c.colony.planet.position
			radius = c.colony.planet.scale * planet_model_radius
			lx = center.x - p1.x
			ly = center.y - p1.y
			lz = center.z - p1.z
			tca = lx*dir_x + ly*dir_y + lz*dir_z
			if tca < 0: continue
			d2 = (lx*lx + ly*ly + lz*lz) - tca*tca
			radius2 = radius * radius
			if d2 > radius2: continue
			thc = math.sqrt(radius2 - d2)
			t0 = tca - thc
			t1 = tca + thc
			if (t0 > 0.1 and t0 < dist) or (t1 > 0.1 and t1 < dist):
				return False
		return True
