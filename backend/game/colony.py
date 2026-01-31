import uuid
import random
import math
import numpy as np
from typing import Optional, List, Dict, Any
from models import ColonyModel, Fleet, ColonyLevel, ColonyTrait, OilPump, SteelFactory, Vector2, Vector3
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
		self._next_factory_id = 1
		self._action_events = []  # Track action events for this colony
		self.last_structure_build_time = 0 # Track last time any structure was built
		self.last_flanker_build_time = 0  # Track last time flankers were built
		self._fleet_patrol_cooldowns = {}  # Track when each fleet last got new patrol waypoints
		self._fleet_waypoint_timers = {}  # Track when each waypoint was set for time-based rotation

	def to_dict(self):
		return self.colony.dict()

	def _distance_v2(self, p1: Vector2, p2: Vector2) -> float:
		"""Calculate euclidean distance between two Vector2 points."""
		return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

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
		if not self.colony.colonyFleet:
			return
		old_count = len(self.colony.colonyFleet)
		self.colony.colonyFleet = [f for f in self.colony.colonyFleet if f.id != fleet_id]
		if len(self.colony.colonyFleet) != old_count:
			self._mark_changed()

	def change_residents(self, delta: int):
		self.colony.residents = max(0, self.colony.residents + delta)
		self._mark_changed()

	def update(self, delta_time: Optional[float] = None) -> None:
		"""Update colony state, including fleets.
		
		Args:
			delta_time: Time since last tick in seconds (for fleet movement).
		"""
		if delta_time is None:
			delta_time = 0.5  # Default tick rate
		
		# Update fleets every tick (movement needs frequent updates)
		self.update_fleets(delta_time)
		
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
		rot = self.colony.planet.rot
		
		# Rotation matrices
		# X-axis rotation
		cx, sx = math.cos(rot.x), math.sin(rot.x)
		y1 = uy * cx - uz * sx
		z1 = uy * sx + uz * cx
		x1 = ux
		
		# Y-axis rotation
		cy, sy = math.cos(rot.y), math.sin(rot.y)
		x2 = x1 * cy + z1 * sy
		z2 = -x1 * sy + z1 * cy
		y2 = y1
		
		# Z-axis rotation
		cz, sz = math.cos(rot.z), math.sin(rot.z)
		x3 = x2 * cz - y2 * sz
		y3 = x2 * sz + y2 * cz
		z3 = z2
		
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
			if self.can_build_flanker_group() and random.random() < 0.2:
				self.build_flanker_group()
		
		# Aggressive: Heavily favors fleets (70% chance to prioritize fleets)
		elif trait == ColonyTrait.Aggressive.value:
			# Prioritize fleet building
			if self.can_build_flanker_group() and random.random() < 0.7:
				self.build_flanker_group()
			# Still build some economic structures (30%)
			else:
				try_build_economy()
		
		# Defensive: Balanced approach (50/50 split between economy and defense)
		elif trait == ColonyTrait.Defensive.value:
			# Random choice between building economic or military
			if random.random() < 0.5:
				# Build economic
				if not try_build_economy():
					# Fallback to fleet if can't build economy
					if self.can_build_flanker_group():
						self.build_flanker_group()
			else:
				# Build fleet
				if self.can_build_flanker_group():
					self.build_flanker_group()
				else:
					# Fallback to economic if can't build fleet
					try_build_economy()
		
		# Default behavior if no trait matched
		else:
			# Balanced approach. Try to build one thing.
			if random.random() < 0.5:
				if not try_build_economy():
					if self.can_build_flanker_group():
						self.build_flanker_group()
			else:
				if self.can_build_flanker_group():
					self.build_flanker_group()
				else:
					try_build_economy()

	def update_fleets(self, delta_time: float):
		"""Update all fleet positions and behaviors."""
		if not self.colony.colonyFleet:
			return
		
		for fleet in self.colony.colonyFleet:
			self._update_fleet_movement(fleet, delta_time)
			self._update_fleet_behavior(fleet)

	def _project_position_to_orbit(self, position: Vector3) -> Vector3:
		"""Project a position onto the safe orbit shell around the planet."""
		planet_pos = self.colony.planet.position
		
		# specific vector from planet center to position
		dx = position.x - planet_pos.x
		dy = position.y - planet_pos.y
		dz = position.z - planet_pos.z
		
		dist = math.sqrt(dx*dx + dy*dy + dz*dz)
		if dist < 0.001:
			dx, dy, dz = 0, 1, 0
			dist = 1.0
			
		# Safe Orbit Radius:
		# Planet Scale * Base Radius (from config) * Safety(1.1) + Fly Altitude (3.0)
		orbit_radius = self.colony.planet.scale * planet_model_radius * 1.1 + 3.0
		
		scale_factor = orbit_radius / dist
		
		return Vector3(
			x=planet_pos.x + dx * scale_factor,
			y=planet_pos.y + dy * scale_factor,
			z=planet_pos.z + dz * scale_factor
		)

	def _update_fleet_movement(self, fleet: Fleet, delta_time: float):
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
			
			# Enforce Orbit Shell Constraint check
			# This prevents the fleet from ever entering the planet
			constrained_pos = self._project_position_to_orbit(Vector3(x=next_x, y=next_y, z=next_z))
			
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
			# Reached waypoint, rotate to next
			first_waypoint = fleet.waypoints.pop(0)
			fleet.waypoints.append(first_waypoint)
			self._mark_changed()
			
			# Update target to new first waypoint for velocity calculation
			target_waypoint = fleet.waypoints[0]
			dx = target_waypoint.x - fleet.position.x
			dy = target_waypoint.y - fleet.position.y
			dz = target_waypoint.z - fleet.position.z
			distance = math.sqrt(dx*dx + dy*dy + dz*dz)
		
		# Calculate velocity towards waypoint (in world space)
		if distance > 0:
			speed = fleet.speed if fleet.speed else 5.0
			
			# If very close, cap speed to avoid massive overshoot in one frame
			# (though the arrival check above handles rotation)
			
			new_velocity = Vector3(
				x=(dx / distance) * speed,
				y=(dy / distance) * speed,
				z=(dz / distance) * speed
			)
			
			# Only update velocity if it changed significantly (reduces broadcasts)
			if (abs(new_velocity.x - fleet.velocity.x) > 0.01 or 
				abs(new_velocity.y - fleet.velocity.y) > 0.01 or 
				abs(new_velocity.z - fleet.velocity.z) > 0.01):
				fleet.velocity = new_velocity
				self._mark_changed()

	def _update_fleet_behavior(self, fleet: Fleet):
		"""Update fleet behavior based on state and trait."""
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
		
		# Pacifist colonies don't move fleets aggressively
		if self.colony.trait == ColonyTrait.Pacifist.value:
			# Just stay near home with minimal patrol
			self._set_patrol_waypoints(fleet, patrol_distance=0.5)
			return
		
		# Other colonies patrol actively but stay near home base
		# Get patrol radius from config based on fleet type
		fleet_stats = _CONFIG.get("fleet_stats", {}).get(fleet.type, {})
		patrol_radius = fleet_stats.get("patrol_radius", 1.0)
		
		self._set_patrol_waypoints(fleet, patrol_distance=patrol_radius)

	def _set_patrol_waypoints(self, fleet: Fleet, patrol_distance: float = 1.0):
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
			
		waypoints = []
		num_waypoints = 8  # More waypoints for smoother circle
		
		center_x = fleet.homePosition.x
		center_y = fleet.homePosition.y  
		center_z = fleet.homePosition.z
		
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
			waypoints.append(wp_projected)
		
		# Return to start
		waypoints.append(waypoints[0])
		
		fleet.waypoints = waypoints
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
