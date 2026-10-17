import random

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
WINDOW_WIDTH = 1912
WINDOW_HEIGHT = 954
BUTTON_X = 776
BUTTON_Y = 496.6875
BUTTON_WIDTH = 360
BUTTON_HEIGHT = 48


# ── Helpers ────────────────────────────────────────────────────

def _random_delta() -> int:
    if random.random() <= 0.7:
        return random.randint(1, 3)
    return random.randint(4, 15)


# ── Solution generator ─────────────────────────────────────────

class Rostile:
    @staticmethod
    def get_solution(challenge_id: str) -> dict:
        start_timestamp = random.uniform(7000, 20000)
        num_movements = random.randint(10, 100)

        click_x = random.randint(BUTTON_X + 2, BUTTON_X + BUTTON_WIDTH)
        click_y = random.randint(int(BUTTON_Y) + 2, int(BUTTON_Y) + BUTTON_HEIGHT)

        current_x = random.randint(500, 800)
        current_y = random.randint(200, 500)
        current_timestamp = start_timestamp

        movements = []

        # Generate random mouse movement path

        for _ in range(num_movements):
            increase_x = random.choice([True, False])
            increase_y = random.choice([True, False])

            if current_x + 15 > WINDOW_WIDTH:
                increase_x = False
            if current_x - 15 < 2:
                increase_x = True

            if current_y + 15 > WINDOW_HEIGHT:
                increase_y = False
            if current_y - 15 < 2:
                increase_y = True

            current_x += _random_delta() if increase_x else -_random_delta()
            current_y += _random_delta() if increase_y else -_random_delta()

            movements.append({
                "x": current_x,
                "y": current_y,
                "timestamp": current_timestamp,
            })

            current_timestamp += random.uniform(10, 60)

        return {
            "challengeId": challenge_id,
            "solution": {
                "buttonClicked": True,
                "click": {
                    "x": click_x,
                    "y": click_y,
                    "timestamp": movements[-1]["timestamp"] - random.uniform(50, 200),
                    "duration": random.uniform(50, 400),
                },
                "completionTime": random.uniform(3000, 15000),
                "mouseMovements": movements,
                "screenSize": {"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
                "buttonLocation": {
                    "x": BUTTON_X,
                    "y": BUTTON_Y,
                    "width": BUTTON_WIDTH,
                    "height": BUTTON_HEIGHT,
                },
                "windowSize": {"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                "isMobile": False,
            },
        }