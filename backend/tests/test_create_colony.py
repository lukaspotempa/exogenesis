from ..game.manager import GameManager


def run_test():
    gm = GameManager()
    # minimal payload, no planet provided
    payload = {
        "name": "Alpha",
        "residents": 100,
        "color": "#ff0000",
        "colonyLevel": "Colony"
    }
    result = gm.create_colony(payload)
    print("Created colony:", result)


if __name__ == '__main__':
    run_test()
