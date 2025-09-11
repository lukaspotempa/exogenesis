from fastapi import FastAPI, WebSocket
from game.connection import ConnectionManager
from game.manager import GameManager
from contextlib import asynccontextmanager



connection_manager = ConnectionManager()
game_manager = GameManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # initialise seed colonies and start the periodic game loop
    game_manager.initialise_game()
    # start the game loop with 200ms tick interval
    await game_manager.start_game_loop(interval=0.2)

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
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")