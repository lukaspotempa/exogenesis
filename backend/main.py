from fastapi import FastAPI, WebSocket
from game.connection import ConnectionManager
from game.manager import GameManager


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Exogenesis backend up"}


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