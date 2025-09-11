from fastapi import FastAPI, WebSocket
from fastapi.websockets import WebSocketDisconnect
import json
from game.connection import ConnectionManager
from game.manager import GameManager
from contextlib import asynccontextmanager


connection_manager = ConnectionManager()
game_manager = GameManager()

# Connect the game manager to the connection manager for broadcasting updates
game_manager.set_connection_manager(connection_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # initialise seed colonies and start the periodic game loop
    game_manager.initialise_game()
    # start the game loop with 500ms tick interval
    await game_manager.start_game_loop(interval=0.5)

    yield

    # stop loop and clear state on shutdown
    await game_manager.stop_game_loop()
    game_manager.clear_colonies()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Exogenesis backend up"}


@app.get('/api/colonies')
def api_list_colonies():
    return game_manager.list_colonies()


@app.post('/api/colonies')
def api_create_colony(payload: dict):
    return game_manager.create_colony(payload)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await connection_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()

            try:
                payload = json.loads(data)
            except Exception:
                payload = data
            if isinstance(payload, dict) and payload.get("initialConnection"):
                snapshot = game_manager.list_colonies()
                await websocket.send_json({"type": "snapshot", "colonies": snapshot})
                continue

            try:
                await websocket.send_text("ack")
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(websocket)
        
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)