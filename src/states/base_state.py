class State:
    """Base class for all application states."""
    def __init__(self, state_manager):
        self.manager = state_manager
        
    def enter(self):
        """Called when the state is transitioned into."""
        pass
        
    def exit(self):
        """Called when the state is transitioned out of."""
        pass
        
    def handle_events(self, events):
        """Process Pygame events (like keyboard inputs)."""
        pass
        
    def update(self, dt):
        """Update logic (math, timers, movement). dt is delta time in seconds."""
        pass
        
    def draw(self, surface):
        """Render graphics to the provided surface."""
        pass
        
    def draw_pomodoro(self, surface, time_left, mode):
        """Draw the Pomodoro overlay uniquely styled for this specific state.
        
        Args:
           surface (pygame.Surface): The surface to draw to.
           time_left (float): The time left in seconds.
           mode (str): 'work' or 'break'.
        """
        pass
