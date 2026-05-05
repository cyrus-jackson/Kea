# --- Configuration ---

# Environment Setup
ENVIRONMENT = "staging" # Can be "development", "staging", "production"

# Screen Sizes
if ENVIRONMENT == "staging":
    SCREEN_WIDTH = 400
    SCREEN_HEIGHT = 600
elif ENVIRONMENT == "production":
    SCREEN_WIDTH = 200
    SCREEN_HEIGHT = 300
else:
    SCREEN_WIDTH = 200
    SCREEN_HEIGHT = 300

FPS = 60

# --- Colors ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
DARK_BLUE = (10, 10, 40)
CRIMSON = (150, 0, 0)
YELLOW_BG = (200, 180, 0)
