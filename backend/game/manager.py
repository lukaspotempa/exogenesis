from typing import List, Optional
from fastapi import HTTPException
import random
import asyncio
import time
from .colony import Colony
import json

PLANET_NAME_POOL = [
    "Aurora", "Mundane", "Mohawk", "Vega", "Solaris", "Erebus", "Nyx", "Hyperion",
    "Elysium", "Tartarus", "Zephyr", "Helios", "Callisto", "Oberon", "Titania",
    "Ariel", "Umbriel", "Triton", "Proteus", "Larissa", "Galatea", "Despina",
    "Thalassa", "Naiad", "Nereid", "Ophelia", "Bianca", "Cressida", "Desdemona",
    "Juliet", "Portia", "Rosalind", "Belinda", "Puck", "Cordelia", "Perdita",
    "Mab", "Cupid", "Setebos", "Sycorax", "Prospero", "Stephano", "Trinculo",
    "Caliban", "Ferdinand", "Enceladus", "Mimas", "Rhea", "Dione", "Tethys",
    "Phoebe", "Janus", "Epimetheus", "Helene", "Telesto", "Calypso", "Kiviuq",
    "Ijiraq", "Paaliaq", "Skathi", "Albiorix", "Bebhionn", "Erriapus", "Siarnaq",
    "Themisto", "Metis", "Adrastea", "Amalthea", "Thebe", "Io", "Ganymede",
    "Himalia", "Elara", "Pasiphae", "Sinope", "Lysithea", "Carme", "Ananke",
    "Leda", "Thebe", "Aether", "Kronos", "Ares", "Hermes", "Athena", "Hestia",
    "Demeter", "Persephone", "Hades", "Poseidon", "Aphrodite", "Nemesis", "Selene",
    "Eos", "Iris", "Moira", "Tyche", "Phoebe", "Circe", "Siren", "Pandora",
]

class GameManager:
    """Manages colonies in-memory."""

    # background task for game loop (None when not running)
    _loop_task: Optional[asyncio.Task] = None

    def __init__(self):
        self.colonies: List[Colony] = []
        self._connection_manager = None
        self.action_history: List[dict] = []  # Store global action history
        self._game_over_announced: bool = False
        self._restart_task: Optional[asyncio.Task] = None

    def set_connection_manager(self, connection_manager):
        """Set the connection manager for broadcasting updates."""
        self._connection_manager = connection_manager

    def initialise_game(self, count: int = 15) -> List[dict]:
        created = []
        default_data = []
        with open('config.json') as f:
            default_data = json.load(f)
        
        # Check for debug scenario
        if default_data.get("use_debug_scenario", False):
            print("Initializing Debug Scenario: 2 planets 150 units apart.")
            return self._create_debug_scenario()

        used_names = {c.colony.name for c in self.colonies}
        available_names = [n for n in PLANET_NAME_POOL if n not in used_names]
        chosen_names = random.sample(available_names, min(count, len(available_names)))

        for name in chosen_names:
            payload = {
                "name": name,
                "residents": default_data["defaultResidents"],
                "color": f"#{random.randint(0, 0xFFFFFF):06x}",
                "colonyLevel": "Colony",
            }
            created.append(self.create_colony(payload))
        return created

    def _create_debug_scenario(self) -> List[dict]:
        """Create a deterministic scenario for testing."""
        self.colonies.clear()
        created = []
        
        # Colony 1: Attacker (Red) - fully maxed out
        c1_payload = {
            "name": "Red Attacker",
            "residents": 50000,
            "color": "#FF0000",
            "colonyLevel": "Starport Hub",
            "trait": "Aggressive",
            "planet": {
                "position": {"x": -75.0, "y": 0.0, "z": 0.0},
                "scale": 1.0,
                "rot": {"x": 0.0, "y": 0.0, "z": 0.0},
                "planetModelName": "Planet_A",
                "planetMainBase": {"x": 0.0, "y": 0.0},
                "planetNaturalResources": {
                    "oil": 5.0, "steel": 5.0, "water": 5.0, "temperature": 15.0,
                    "oilStorage": 99999.0, "steelStorage": 99999.0, "waterStorage": 99999.0
                },
                "oilPumps": [
                    {"id": "init_pump_1", "position": {"x": 0.1, "y": 0.1}, "production": 5.0},
                    {"id": "init_pump_2", "position": {"x": -0.2, "y": 0.2}, "production": 5.0},
                    {"id": "init_pump_3", "position": {"x": 0.2, "y": -0.2}, "production": 5.0}
                ]
            }
        }
        
        # Colony 2: Defender (Blue) - bare Colony, barely alive
        c2_payload = {
            "name": "Blue Defender",
            "residents": 100,
            "color": "#0055FF",
            "colonyLevel": "Colony",
            "trait": "Defensive",
            "planet": {
                "position": {"x": 75.0, "y": 0.0, "z": 0.0},
                "scale": 1.0,
                "rot": {"x": 0.0, "y": 0.0, "z": 0.0},
                "planetModelName": "Planet_B",
                "planetMainBase": {"x": 0.0, "y": 0.0},
                "planetNaturalResources": {
                    "oil": 0.5, "steel": 0.5, "water": 0.5, "temperature": 15.0,
                    "oilStorage": 250.0, "steelStorage": 300.0, "waterStorage": 300.0
                },
                "oilPumps": []
            }
        }
        
        c1 = self.create_colony(c1_payload)
        c2 = self.create_colony(c2_payload)
        
        # Manually trigger initial fleet builds for testing
        # We need to access the Colony OBJECTS, not the dicts returned by create_colony
        c1_obj = self.colonies[-2] # Red
        c2_obj = self.colonies[-1] # Blue
        
        # Give Red a full armada
        for _ in range(5):
            c1_obj.build_flanker_group()
        for _ in range(3):
            c1_obj.build_bomber_group()
        for _ in range(3):
            c1_obj.build_fighter_group()
        c1_obj.build_scout_group()
        
        # Blue gets nothing — it will be overwhelmed

        created.append(c1)
        created.append(c2)
        return created
    
    def clear_colonies(self):
        self.colonies.clear()

    async def start_game_loop(self, interval: float = 0.05) -> None:
        """Start a background task that calls tick() every `interval` seconds.
        """
        if self._loop_task is not None and not self._loop_task.done():
            return

        async def _runner():
            try:
                while True:
                    try:
                        self.tick(delta_time=interval)
                    except Exception:
                        # swallow exceptions from tick to keep loop alive
                        pass
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                return

        self._loop_task = asyncio.create_task(_runner())

    async def stop_game_loop(self) -> None:
        """Stop the background game loop task if running."""
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            pass
        self._loop_task = None

    def tick(self, delta_time: float = 0.5) -> None:
        changes = []
        all_action_events = []
        
        # Pass all colonies to update so they can interact (combat)
        all_colonies_ref = self.colonies
        
        for c in self.colonies:
            try:
                c.update(delta_time, all_colonies_ref)
                # Check for changes after update
                colony_changes = c.get_changes()
                if colony_changes:
                    changes.append(colony_changes)
                
                # Collect action events from the colony
                action_events = c.get_action_events()
                all_action_events.extend(action_events)
            except Exception as e:
                print(f"Error updating colony: {e}")
                continue
        
        # Check Win Condition
        self._check_win_condition(all_action_events)

        # Update global history
        if all_action_events:
            self.action_history.extend(all_action_events)
            # Keep only the last 50 events
            if len(self.action_history) > 50:
                self.action_history = self.action_history[-50:]
        
        # Broadcast changes to all connected clients
        if changes and self._connection_manager:
            asyncio.create_task(self._broadcast_changes(changes))
        
        # Broadcast action events to all connected clients
        if all_action_events and self._connection_manager:
            asyncio.create_task(self._broadcast_action_events(all_action_events))

    def _check_win_condition(self, events_list: List[dict]):
        """Check if one colony has taken over all others."""
        if not self.colonies or self._game_over_announced:
            return

        owners = set()
        for c in self.colonies:
            owner = c.colony.owner_id if c.colony.owner_id else c.colony.id
            owners.add(owner)

        if len(owners) == 1 and len(self.colonies) > 1:
            winner_id = list(owners)[0]
            winner_colony = next((c for c in self.colonies if c.colony.id == winner_id), None)
            winner_name = winner_colony.colony.name if winner_colony else "Unknown"
            winner_color = winner_colony.colony.color if winner_colony else "#ffffff"

            self._game_over_announced = True
            restart_at = time.time() + 60  # 60-second cooldown

            game_over_msg = {
                "type": "game_over",
                "winner": {
                    "id": winner_id,
                    "name": winner_name,
                    "color": winner_color,
                },
                "actionHistory": list(self.action_history),
                "restartAt": restart_at,
            }

            if self._connection_manager:
                asyncio.create_task(self._connection_manager.broadcast_json(game_over_msg))

            # Schedule game reset after cooldown
            self._restart_task = asyncio.create_task(self._schedule_restart(60))

    async def _schedule_restart(self, delay: float) -> None:
        """Wait `delay` seconds, then reset and restart the game."""
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        # Stop the current game loop
        await self.stop_game_loop()

        # Clear all state
        self.colonies.clear()
        self.action_history.clear()
        self._game_over_announced = False
        self._restart_task = None

        # Re-initialise and start a fresh game
        self.initialise_game()
        await self.start_game_loop(interval=0.5)

        # Broadcast a snapshot so all clients pick up the new game
        if self._connection_manager:
            snapshot = {
                "type": "snapshot",
                "colonies": self.list_colonies(),
                "actionEvents": [],
            }
            await self._connection_manager.broadcast_json(snapshot)

    async def _broadcast_changes(self, changes: List[dict]) -> None:
        """Broadcast colony changes to all connected clients."""
        if not self._connection_manager:
            return
        
        update_message = {
            "type": "update",
            "changes": changes,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        await self._connection_manager.broadcast_json(update_message)

    async def _broadcast_action_events(self, events: List[dict]) -> None:
        """Broadcast action events to all connected clients."""
        if not self._connection_manager:
            return
        
        # Send each event separately for better real-time feedback
        for event in events:
            action_message = {
                "type": "action",
                "event": event
            }
            await self._connection_manager.broadcast_json(action_message)

    def list_colonies(self) -> List[dict]:
        return [c.to_dict() for c in self.colonies]

    def get_action_history(self) -> List[dict]:
        return self.action_history

    def create_colony(self, payload: dict) -> dict:
        try:
            entity = Colony.create_colony(payload, self.colonies)
            self.colonies.append(entity)
            return entity.to_dict()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
