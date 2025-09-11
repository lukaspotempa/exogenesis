from typing import List, Optional
from fastapi import HTTPException
import uuid
import random
import math
import numpy as np
import asyncio
from ..models import ColonyModel, Planet
from .colony import Colony


class GameManager:
    """Manages colonies in-memory."""

    # background task for game loop (None when not running)
    _loop_task: Optional[asyncio.Task] = None

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

    async def start_game_loop(self, interval: float = 0.5) -> None:
        """Start a background task that calls tick() every `interval` seconds.

        Safe to call multiple times; subsequent calls while running are no-ops.
        """
        if self._loop_task is not None and not self._loop_task.done():
            return

        async def _runner():
            try:
                while True:
                    try:
                        self.tick()
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

    def tick(self) -> None:
        for c in self.colonies:
            try:
                c.update()
            except Exception:
                continue

    def list_colonies(self) -> List[dict]:
        return [c.to_dict() for c in self.colonies]

    def create_colony(self, payload: dict) -> dict:
        try:
            entity = Colony.create_colony(payload, self.colonies)
            self.colonies.append(entity)
            return entity.to_dict()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
