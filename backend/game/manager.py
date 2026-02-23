from typing import List, Optional
from fastapi import HTTPException
import random
import asyncio
from .colony import Colony
import json

colony_names = ["Aurora", "Mundane", "Mohawk", "Mohawk"]

class GameManager:
    """Manages colonies in-memory."""

    # background task for game loop (None when not running)
    _loop_task: Optional[asyncio.Task] = None

    def __init__(self):
        self.colonies: List[Colony] = []
        self._connection_manager = None
        self.action_history: List[dict] = []  # Store global action history

    def set_connection_manager(self, connection_manager):
        """Set the connection manager for broadcasting updates."""
        self._connection_manager = connection_manager

    def initialise_game(self, count: int = 3) -> List[dict]:
        created = []
        default_data = []
        with open('config.json') as f:
            default_data = json.load(f)
        
        # Check for debug scenario
        if default_data.get("use_debug_scenario", False):
            print("Initializing Debug Scenario: 2 planets 150 units apart.")
            return self._create_debug_scenario()
            
        for i in range(count):
            payload = {
                "name": colony_names[len(self.colonies)],
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
        
        # Colony 1: Attacker (Red) at (-75, 0, 0)
        c1_payload = {
            "name": "Red Attacker",
            "residents": 1000,
            "color": "#FF0000",
            "colonyLevel": "Metropolis", # High level
            "trait": "Aggressive",
            "planet": {
                "position": {"x": -75.0, "y": 0.0, "z": 0.0},
                "scale": 1.0,
                "rot": {"x": 0.0, "y": 0.0, "z": 0.0},
                "planetModelName": "Planet_A",
                "planetMainBase": {"x": 0.0, "y": 0.0}, # Centered base
                "planetNaturalResources": {
                    "oil": 2.0, "steel": 2.0, "water": 2.0, "temperature": 15.0,
                    "oilStorage": 9000.0, "steelStorage": 9000.0, "waterStorage": 9000.0 # Plenty of resources
                },
                "oilPumps": [{"id": "init_pump_1", "position": {"x": 0.1, "y": 0.1}, "production": 1.0}] # Ensure requirements met
            }
        }
        
        # Colony 2: Defender (Blue) at (75, 0, 0)
        c2_payload = {
            "name": "Blue Defender",
            "residents": 1000,
            "color": "#0000FF",
            "colonyLevel": "Metropolis",
            "trait": "Defensive",
            "planet": {
                "position": {"x": 75.0, "y": 0.0, "z": 0.0},
                "scale": 1.0,
                "rot": {"x": 0.0, "y": 0.0, "z": 0.0},
                "planetModelName": "Planet_B",
                "planetMainBase": {"x": 0.0, "y": 0.0},
                "planetNaturalResources": {
                    "oil": 2.0, "steel": 2.0, "water": 2.0, "temperature": 15.0,
                    "oilStorage": 9000.0, "steelStorage": 9000.0, "waterStorage": 9000.0
                },
                "oilPumps": [{"id": "init_pump_2", "position": {"x": 0.1, "y": 0.1}, "production": 1.0}]
            }
        }
        
        c1 = self.create_colony(c1_payload)
        c2 = self.create_colony(c2_payload)
        
        # Manually trigger initial fleet builds for testing
        # We need to access the Colony OBJECTS, not the dicts returned by create_colony
        c1_obj = self.colonies[-2] # Red
        c2_obj = self.colonies[-1] # Blue
        
        # Give Red some ships
        c1_obj.build_flanker_group()
        c1_obj.build_bomber_group()
        c1_obj.build_scout_group()
        
        # Give Blue some ships
        c2_obj.build_fighter_group()
        c2_obj.build_scout_group()

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
        if not self.colonies:
            return

        # Group by owner
        owners = set()
        active_owners = set()
        
        for c in self.colonies:
            owner = c.colony.owner_id if c.colony.owner_id else c.colony.id
            owners.add(owner)
            # Consider a colony 'active' if it has not been taken over (owner_id == id)
            # OR just strictly check if everyone has the same owner.
        
        if len(owners) == 1 and len(self.colonies) > 1:
            winner_id = list(owners)[0]
            winner_name = next((c.colony.name for c in self.colonies if c.colony.id == winner_id), "Unknown")
            
            # Check if we already broadcasted win (could use a flag in GameManager)
            # For now, let's just emit an event if not just emitted.
            # Ideally we stop the game or pause it, or just notify.
            # Let's add a 'GAME OVER' event.
            
            # Simple debounce or check state required to not spam? 
            # Assuming the frontend handles "Game Over" gracefully or we just spam it every tick (bad).
            # Let's check if we have a winner and haven't announced it.
            # Since I don't have game state persistence for 'finished', I'll just check if it's a NEW win condition.
            # But 'owners' will be 1 forever after win.
            
            # Maybe just send a special event type "game_over"
            # But I'll append to events_list for now.
            
            # To prevent spam, I'll store 'game_over' state
            if not getattr(self, '_game_over_announced', False):
                 events_list.append({
                    "id": "game-over",
                    "timestamp": asyncio.get_event_loop().time(),
                    "colonyId": winner_id,
                    "colonyName": winner_name,
                    "message": f"{winner_name} has conquered the galaxy!",
                    "type": "victory"
                })
                 self._game_over_announced = True

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
