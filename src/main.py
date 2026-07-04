import pygame
import sys
from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, FULLSCREEN, SCALED, ROTATION
from states.ambient_state import AmbientState
from states.pomodoro_state import PomodoroState
from states.notification_state import NotificationState
from states.telegraph_state import TelegraphState
from states.climate_state import ClimateState
from states.greetings_state import GreetingsState
from states.conservatory_state import ConservatoryState
from states.orbital_state import OrbitalState
from hardware_input import (
    HardwareButtons,
    BUTTON_AMBIENT_EVENT,
    BUTTON_POMODORO_EVENT,
    BUTTON_NOTIFICATION_EVENT,
)


# --- State Manager ---
class StateManager:
    """Manages the active state and transitions between them."""
    def __init__(self):
        self.states = {}
        self.state_names = []
        self.current_state = None
        self.current_state_name = None
        
    def add_state(self, name, state):
        self.states[name] = state
        if name not in self.state_names:
            self.state_names.append(name)
        
    def change_state(self, name):
        if self.current_state:
            self.current_state.exit()
            
        self.current_state = self.states.get(name)
        self.current_state_name = name
        
        if self.current_state:
            self.current_state.enter()

    def next_state(self):
        """Cycles to the next available state sequentially."""
        if not self.state_names:
            return
        if self.current_state_name in self.state_names:
            current_index = self.state_names.index(self.current_state_name)
            next_index = (current_index + 1) % len(self.state_names)
        else:
            next_index = 0
            
        self.change_state(self.state_names[next_index])
            
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
    # Pre-init mixer to avoid ALSA underrun errors
    pygame.mixer.pre_init(44100, -16, 2, 4096)
    pygame.init()
    
    # 200x300 Display Surface
    flags = 0
    if FULLSCREEN:
        flags |= pygame.FULLSCREEN
    if SCALED:
        flags |= pygame.SCALED

    # If rotated 90 or 270, swap dimensions for the physical screen
    if ROTATION in (90, 270):
        physical_width, physical_height = SCREEN_HEIGHT, SCREEN_WIDTH
    else:
        physical_width, physical_height = SCREEN_WIDTH, SCREEN_HEIGHT

    screen = pygame.display.set_mode((physical_width, physical_height), flags)
    logical_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    
    pygame.display.set_caption("Smart Display")

    if FULLSCREEN:
        pygame.mouse.set_visible(False)
    
    clock = pygame.time.Clock()
    
    # Setup State Manager
    manager = StateManager()
    manager.add_state('ambient', AmbientState(manager))
    manager.add_state('pomodoro', PomodoroState(manager))
    manager.add_state('notification', NotificationState(manager))
    manager.add_state('telegraph', TelegraphState(manager))
    manager.add_state('climate', ClimateState(manager))
    manager.add_state('greetings', GreetingsState(manager))
    manager.add_state('conservatory', ConservatoryState(manager))
    manager.add_state('orbital', OrbitalState(manager))
    
    # Start in Ambient State
    manager.change_state('ambient')
    
    # Initialize hardware button poller
    hw_buttons = HardwareButtons()
    
    running = True
    while running:
        # Time management
        dt = clock.tick(FPS) / 1000.0 # Convert milliseconds to seconds
        
        # Poll hardware buttons each frame
        hw_buttons.update()
        
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            
            # Handle Custom Hardware Button Events
            elif event.type == BUTTON_AMBIENT_EVENT:
                manager.next_state()  # Cycle to the next state
            elif event.type == BUTTON_POMODORO_EVENT:
                if manager.current_state_name != 'pomodoro':
                    manager.change_state('pomodoro')
            elif event.type == BUTTON_NOTIFICATION_EVENT:
                if manager.current_state_name != 'pomodoro':
                    manager.change_state('notification')
            
            # Global Key Inputs for Testing
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_1:
                    manager.change_state('ambient')
                elif event.key == pygame.K_2:
                    if manager.current_state_name != 'pomodoro':
                        manager.change_state('pomodoro')
                    else:
                        pygame.event.post(pygame.event.Event(BUTTON_POMODORO_EVENT))
                elif event.key == pygame.K_3:
                    if manager.current_state_name != 'pomodoro':
                        manager.change_state('notification')
                    else:
                        pygame.event.post(pygame.event.Event(BUTTON_NOTIFICATION_EVENT))
                elif event.key == pygame.K_4:
                    manager.change_state('orbital')
                elif event.key == pygame.K_6:
                    manager.change_state('telegraph')
                elif event.key == pygame.K_7:
                    manager.change_state('conservatory')
                elif event.key == pygame.K_8:
                    manager.change_state('climate')
                elif event.key == pygame.K_9:
                    manager.change_state('greetings')
        
        # State-specific event handling
        manager.handle_events(events)
        
        # Update
        manager.update(dt)
        
        # Ensure Pomodoro updates in the background if it's active but not the current state
        if manager.current_state_name != 'pomodoro':
            pomodoro_state_obj = manager.states.get('pomodoro')
            if pomodoro_state_obj:
                pomodoro_state_obj.update(dt)
        
        # Clear the logical surface to prevent trails
        logical_surface.fill((0, 0, 0))
        
        # Draw to the logical surface
        manager.draw(logical_surface)
        
        # Display global Pomodoro overlay if running
        if manager.current_state_name != 'pomodoro':
            pomodoro_state_obj = manager.states.get('pomodoro')
            if pomodoro_state_obj and pomodoro_state_obj.running:
                if hasattr(manager.current_state, 'draw_pomodoro'):
                    manager.current_state.draw_pomodoro(logical_surface, pomodoro_state_obj.time_left, pomodoro_state_obj.mode)
                else:
                    pomodoro_state_obj.draw_overlay(logical_surface)
        
        # Rotate and blit to screen
        if ROTATION != 0:
            rotated_surface = pygame.transform.rotate(logical_surface, ROTATION)
            screen.blit(rotated_surface, (0, 0))
        else:
            screen.blit(logical_surface, (0, 0))
        
        # Update the full display Surface to the screen
        pygame.display.flip()
        
    hw_buttons.cleanup()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
