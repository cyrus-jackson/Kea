import pygame
import sys
from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from states.ambient_state import AmbientState
from states.pomodoro_state import PomodoroState
from states.notification_state import NotificationState



# --- State Manager ---
class StateManager:
    """Manages the active state and transitions between them."""
    def __init__(self):
        self.states = {}
        self.current_state = None
        
    def add_state(self, name, state):
        self.states[name] = state
        
    def change_state(self, name):
        if self.current_state:
            self.current_state.exit()
            
        self.current_state = self.states.get(name)
        
        if self.current_state:
            self.current_state.enter()
            
    def handle_events(self, events):
        if self.current_state:
            self.current_state.handle_events(events)
            
    def update(self, dt):
        if self.current_state:
            self.current_state.update(dt)
            
    def draw(self, surface):
        if self.current_state:
            self.current_state.draw(surface)

# --- Main App ---
def main():
    pygame.init()
    
    # 200x300 Display Surface
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Smart Display")
    
    clock = pygame.time.Clock()
    
    # Setup State Manager
    manager = StateManager()
    manager.add_state('ambient', AmbientState(manager))
    manager.add_state('pomodoro', PomodoroState(manager))
    manager.add_state('notification', NotificationState(manager))
    
    # Start in Ambient State
    manager.change_state('ambient')
    
    running = True
    while running:
        # Time management
        dt = clock.tick(FPS) / 1000.0 # Convert milliseconds to seconds
        
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            
            # Global Key Inputs for Testing
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    manager.change_state('ambient')
                elif event.key == pygame.K_2:
                    manager.change_state('pomodoro')
                elif event.key == pygame.K_3:
                    manager.change_state('notification')
        
        # State-specific event handling
        manager.handle_events(events)
        
        # Update
        manager.update(dt)
        
        # Draw
        manager.draw(screen)
        
        # Update the full display Surface to the screen
        pygame.display.flip()
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
