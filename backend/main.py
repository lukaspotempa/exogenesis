from fastapi import FastAPI, WebSocket, HTTPException
from models import Colony, Planet, Vector3, NaturalResources, Vector2, Colony, ColonyModel, Fleet, FleetOrder
from typing import List
from random import choice
import uuid


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Exogenesis backend up"}


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


class GameManager:
    """Manages colonies in-memory. This is intentionally simple and synchronous.

    """

    def __init__(self):
        self.colonies: List[Colony] = []

    def list_colonies(self) -> List[dict]:
        return [c.to_dict() for c in self.colonies]

    def create_colony(self, payload: dict) -> dict:
        # Accept a partial dict and validate via pydantic
        try:
            # ensure id if not provided
            if 'id' not in payload or not payload.get('id'):
                payload['id'] = str(uuid.uuid4())

            # Build Pydantic Colony model (will raise ValidationError on bad data)
            colony_model = ColonyModel(**payload)
            entity = Colony(colony_model)
            self.colonies.append(entity)
            return entity.to_dict()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


manager = ConnectionManager()
game_manager = GameManager()


@app.get('/api/colonies')
def api_list_colonies():
    return game_manager.list_colonies()


@app.post('/api/colonies')
def api_create_colony(payload: dict):
    return game_manager.create_colony(payload)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")