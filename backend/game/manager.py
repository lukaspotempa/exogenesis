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

    def set_connection_manager(self, connection_manager):
        """Set the connection manager for broadcasting updates."""
        self._connection_manager = connection_manager

    def initialise_game(self, count: int = 3) -> List[dict]:
        created = []
        default_data = []
        with open('config.json') as f:
            default_data = json.load(f)
        
        for i in range(count):
            payload = {
                "name": colony_names[len(self.colonies)],
                "residents": default_data["defaultResidents"],
                "color": f"#{random.randint(0, 0xFFFFFF):06x}",
                "colonyLevel": "Colony",
            }
            created.append(self.create_colony(payload))
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
        for c in self.colonies:
            try:
                c.update(delta_time)
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
        
        # Broadcast changes to all connected clients
        if changes and self._connection_manager:
            asyncio.create_task(self._broadcast_changes(changes))
        
        # Broadcast action events to all connected clients
        if all_action_events and self._connection_manager:
            asyncio.create_task(self._broadcast_action_events(all_action_events))

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

    def create_colony(self, payload: dict) -> dict:
        try:
            entity = Colony.create_colony(payload, self.colonies)
            self.colonies.append(entity)
            return entity.to_dict()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
