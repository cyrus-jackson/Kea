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
from states.biolab_state import BiolabState
from states.abyssal_state import AbyssalState
from states.nexus_state import NexusState
from states.aerodrome_state import AerodromeState
from states.docket_state import DocketState
from states.orrery_state import OrreryState
from states.starport_state import StarportState
from states.logbook_state import LogbookState
from backend import voice
from backend import lifebook
from hardware_input import (
    HardwareButtons,
    BUTTON_AMBIENT_EVENT,
    BUTTON_POMODORO_EVENT,
    BUTTON_NOTIFICATION_EVENT,
    ENCODER_TURN_EVENT,
    ENCODER_PRESS_EVENT,
    TOGGLE_EVENT,
    TOGGLE_ROLE,
)
from states.nexus_state import WORLDS


def _tune(manager, direction):
    """Encoder turned outside Nexus: tune through the worlds like a dial."""
    names = [w[0] for w in WORLDS]
    try:
        i = names.index(manager.current_state_name)
    except ValueError:
        i = 0 if direction > 0 else len(names) - 1
        manager.change_state(names[i])
        return
    manager.change_state(names[(i + direction) % len(names)])


# --- State Manager ---
class StateManager:
    """Manages the active state and transitions between them."""
    def __init__(self):
        self.states = {}
        self.state_names = []
        self.current_state = None
        self.current_state_name = None
        self.previous_state_name = None   # so transient states can go back

    def add_state(self, name, state):
        self.states[name] = state
        if name not in self.state_names:
            self.state_names.append(name)
        
    def change_state(self, name):
        if self.current_state:
            self.current_state.exit()

        if name != self.current_state_name:
            self.previous_state_name = self.current_state_name
            voice.say("blip")          # soft acknowledgment, rate-limited

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
    # Pre-init mixer to avoid ALSA underrun errors. 1024 keeps Kea's
    # chirps snappy (~23 ms) instead of lagging a tenth of a second.
    pygame.mixer.pre_init(44100, -16, 2, 1024)
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
    manager.add_state('biolab', BiolabState(manager))
    manager.add_state('abyssal', AbyssalState(manager))
    manager.add_state('nexus', NexusState(manager))
    manager.add_state('aerodrome', AerodromeState(manager))
    manager.add_state('docket', DocketState(manager))
    manager.add_state('orrery', OrreryState(manager))
    manager.add_state('starport', StarportState(manager))
    manager.add_state('logbook', LogbookState(manager))
    lifebook.bump('boots')

    # Kea's voice: synthesised in the background, greets us when ready
    voice.init()
    voice.say_when_ready('wake')
    
    # Boot into the Nexus home hub
    manager.change_state('nexus')
    
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
                # states may consume the green button (e.g. the Docket
                # stamps a reminder DONE); otherwise it opens notification
                cur = manager.current_state
                if cur is not None and hasattr(cur, 'on_green_button') \
                        and cur.on_green_button():
                    pass
                elif manager.current_state_name != 'pomodoro':
                    manager.change_state('notification')
            
            # --- Rotary encoder: browse on Nexus, tune elsewhere ---
            elif event.type == ENCODER_TURN_EVENT:
                cur = manager.current_state
                if manager.current_state_name == 'nexus' and \
                        hasattr(cur, 'move_cursor'):
                    cur.move_cursor(event.direction)
                else:
                    _tune(manager, event.direction)
            elif event.type == ENCODER_PRESS_EVENT:
                cur = manager.current_state
                if manager.current_state_name == 'nexus' and \
                        hasattr(cur, 'activate') and cur.activate():
                    pass
                else:
                    manager.change_state('nexus')   # press = go home
            elif event.type == TOGGLE_EVENT:
                if TOGGLE_ROLE == 'mute':
                    voice.set_muted(event.on)
                elif TOGGLE_ROLE == 'autopilot':
                    nx = manager.states.get('nexus')
                    if nx is not None:
                        nx.auto_pilot = event.on
                        nx.dwell = 0.0
                        if event.on and manager.current_state_name != 'nexus':
                            manager.change_state('nexus')
                voice.say('question' if event.on else 'blip')

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
                elif event.key == pygame.K_5:
                    manager.change_state('biolab')
                elif event.key == pygame.K_0:
                    manager.change_state('abyssal')
                elif event.key == pygame.K_h:
                    manager.change_state('nexus')
                elif event.key == pygame.K_d:
                    manager.change_state('aerodrome')
                elif event.key == pygame.K_r:
                    manager.change_state('docket')
                elif event.key == pygame.K_o:
                    manager.change_state('orrery')
                elif event.key == pygame.K_s:
                    manager.change_state('starport')
                elif event.key == pygame.K_l:
                    manager.change_state('logbook')
                elif event.key == pygame.K_m:
                    voice.toggle_mute()
                # desktop stand-ins for the deck hardware
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    d = 1 if event.key == pygame.K_RIGHT else -1
                    pygame.event.post(pygame.event.Event(ENCODER_TURN_EVENT,
                                                         direction=d))
                elif event.key == pygame.K_RETURN:
                    pygame.event.post(pygame.event.Event(ENCODER_PRESS_EVENT))
                elif event.key == pygame.K_t:
                    nx = manager.states.get('nexus')
                    on = not (nx.auto_pilot if nx else False) \
                        if TOGGLE_ROLE == 'autopilot' else not voice.is_muted()
                    pygame.event.post(pygame.event.Event(TOGGLE_EVENT, on=on))
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
