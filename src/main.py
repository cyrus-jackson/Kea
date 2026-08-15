import os
# Route pygame/SDL audio through PulseAudio so Kea's voice reaches the
# default sink (e.g. the Bluetooth speaker). Without this SDL opens ALSA
# directly and you hear nothing even though `paplay` works. Override by
# exporting SDL_AUDIODRIVER yourself before launch.
os.environ.setdefault("SDL_AUDIODRIVER", "pulseaudio")
# ...and point at the user's PulseAudio socket. A screen/SSH/systemd launch
# often lacks XDG_RUNTIME_DIR, so SDL can't find the running server and stays
# silent — while a desktop-session launch works. Set it if the dir exists.
if hasattr(os, "getuid"):
    _rundir = "/run/user/%d" % os.getuid()
    if os.path.isdir(_rundir):
        os.environ.setdefault("XDG_RUNTIME_DIR", _rundir)

# Set the output volume once at startup, e.g. KEA_START_VOLUME=20 (percent of
# the current default sink — the Bluetooth speaker). Unset = leave it alone.
_start_vol = os.getenv("KEA_START_VOLUME", "").strip()
if _start_vol.isdigit():
    try:
        import subprocess
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@",
                        "%d%%" % int(_start_vol)], check=False, timeout=5)
    except Exception:
        pass       # no pactl / no server: not worth failing the app over

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
from states.console_state import ConsoleState
from states.camera_state import CameraState
from backend import voice
from backend import lifebook
from backend import settings
from hardware_input import (
    HardwareButtons,
    BUTTON_AMBIENT_EVENT,
    BUTTON_POMODORO_EVENT,
    BUTTON_NOTIFICATION_EVENT,
    ENCODER_TURN_EVENT,
    ENCODER_PRESS_EVENT,
    TOGGLE_EVENT,
    TOGGLE_ROLE,
    BUTTON_HOME_EVENT,
    BUTTON_CAMERA_EVENT,
    TOGGLE2_EVENT,
    TOGGLE2_ROLE,
)
from states.nexus_state import WORLDS, NO_CYCLE, cycle_worlds


_chip_font = None
CHIP_SHOW = 2.6      # seconds the label is readable
CHIP_FADE = 0.6      # then it fades out over this long


def _draw_toggle_chip(surface, manager):
    """Transient badge naming what the physical toggle does here.

    It is deliberately NOT permanent. Drawn every frame it sat on top of
    whatever the screen wanted that corner for — several screens put their
    own status text there. So it appears when you arrive or flip the
    lever, then fades, leaving only a 3 px pip when the toggle is engaged.

    Anything an overlay wants to draw belongs in the reserved strip along
    the bottom edge — see docs/UI_GUIDELINES.md.
    """
    cur = manager.current_state
    if cur is None or not hasattr(cur, 'toggle_label'):
        return
    label = cur.toggle_label()
    if not label:
        return

    global _chip_font
    scale = surface.get_height() / 480.0
    if _chip_font is None:
        _chip_font = pygame.font.Font(None, max(11, int(14 * scale)))

    on = manager.toggle_on
    age = getattr(manager, 'chip_age', 999.0)
    pad = max(3, int(5 * scale))
    x = max(3, int(6 * scale))

    if age > CHIP_SHOW + CHIP_FADE:
        # long past: just a small pip so the lever's state is still legible
        if on:
            r = max(2, int(3 * scale))
            pygame.draw.circle(surface, (240, 208, 90),
                               (x + r, surface.get_height() - r - pad), r)
        return

    alpha = 1.0 if age <= CHIP_SHOW else 1.0 - (age - CHIP_SHOW) / CHIP_FADE
    alpha = max(0.0, min(1.0, alpha))
    fg = (18, 18, 20) if on else (150, 155, 165)
    bg = (240, 208, 90) if on else (30, 32, 38)
    txt = _chip_font.render(("▲ " if on else "▽ ") + label, True, fg)
    rect = txt.get_rect()
    box = pygame.Rect(x, surface.get_height() - rect.h - pad * 2 - max(3, int(5 * scale)),
                      rect.w + pad * 2, rect.h + pad * 2)
    chip = pygame.Surface(box.size, pygame.SRCALPHA)
    chip.fill((*bg, int((235 if on else 150) * alpha)))
    surface.blit(chip, box.topleft)
    if on:
        edge = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(edge, (255, 240, 170, int(255 * alpha)),
                         edge.get_rect(), 1)
        surface.blit(edge, box.topleft)
    txt.set_alpha(int(255 * alpha))
    surface.blit(txt, (box.x + pad, box.y + pad))


def _tune(manager, direction):
    """Encoder turned outside Nexus: tune through the worlds like a dial.
    Skips NO_CYCLE screens (Console) — those are Nexus-only."""
    names = [w[0] for w in cycle_worlds()]
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
        self.toggle_on = False            # physical switch position
        self.toggle2_on = False           # second (global) switch
        self.chip_age = 0.0               # how long the toggle chip has shown

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
        self.chip_age = 0.0        # re-announce the lever on the new screen
        
        if self.current_state:
            self.current_state.enter()
            # a position switch means what it points at: re-apply it so the
            # new screen's mode always matches where the lever actually is
            if hasattr(self.current_state, 'on_toggle'):
                try:
                    self.current_state.on_toggle(self.toggle_on)
                except Exception:
                    pass

    def next_state(self):
        """Cycle to the next state, skipping the Nexus-only ones."""
        names = [n for n in self.state_names if n not in NO_CYCLE]
        if not names:
            return
        if self.current_state_name in names:
            i = (names.index(self.current_state_name) + 1) % len(names)
        else:
            i = 0
        self.change_state(names[i])
            
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
    _dim_layer = None          # reused black veil for software brightness
    
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
    manager.add_state('console', ConsoleState(manager))
    manager.add_state('camera', CameraState(manager))
    settings.init()             # restore the saved brightness
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
            
            # --- 4th / 5th buttons: jump straight to a screen ---
            elif event.type == BUTTON_HOME_EVENT:
                manager.change_state('nexus')
            elif event.type == BUTTON_CAMERA_EVENT:
                # Straight to the camera — the shutter is the GREEN button
                # once you're there, so this is one press from anywhere.
                manager.change_state('camera')
            # --- Toggle B: global, screens never claim it ---
            elif event.type == TOGGLE2_EVENT:
                manager.toggle2_on = event.on
                if TOGGLE2_ROLE == 'mute':
                    voice.set_muted(event.on)
                elif TOGGLE2_ROLE == 'autopilot':
                    nx = manager.states.get('nexus')
                    if nx is not None:
                        nx.auto_pilot = event.on
                        nx.dwell = 0.0

            # --- Rotary encoder: browse on Nexus, tune elsewhere ---
            elif event.type == ENCODER_TURN_EVENT:
                cur = manager.current_state
                # Nexus browses its rail; the Console drives its dials;
                # everywhere else the knob tunes through the worlds.
                # A screen that implements move_cursor() owns the dial —
                # Nexus browses, Console adjusts, Camera picks the tag.
                # Anywhere else the knob tunes between worlds. (This used to
                # be a hardcoded ('nexus','console') list, which silently
                # stole the dial from the camera screen.)
                if hasattr(cur, 'move_cursor'):
                    cur.move_cursor(event.direction)
                else:
                    _tune(manager, event.direction)
            elif event.type == ENCODER_PRESS_EVENT:
                cur = manager.current_state
                # Same for the press: the screen gets first refusal, and
                # returning False means "I'm done, take me home".
                if hasattr(cur, 'activate') and cur.activate():
                    pass
                else:
                    manager.change_state('nexus')   # press = go home
            elif event.type == TOGGLE_EVENT:
                manager.toggle_on = event.on
                manager.chip_age = 0.0        # show the label again
                cur = manager.current_state
                # the screen you're on gets first refusal on the switch
                if cur is not None and hasattr(cur, 'on_toggle'):
                    cur.on_toggle(event.on)
                elif TOGGLE_ROLE == 'mute':
                    voice.set_muted(event.on)
                elif TOGGLE_ROLE == 'autopilot':
                    nx = manager.states.get('nexus')
                    if nx is not None:
                        nx.auto_pilot = event.on
                        nx.dwell = 0.0
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
        manager.chip_age += dt
        
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

        # Toggle indicator: the lever's meaning changes per screen, so say
        # what it's doing here. Drawn centrally to stay consistent.
        _draw_toggle_chip(logical_surface, manager)

        # Brightness. If the panel exposes a real backlight, settings already
        # wrote it and this is a no-op; otherwise (most SPI TFTs, whose LED
        # line is tied to 3V3) we dim by veiling the frame in black.
        veil = settings.dim_alpha()
        if veil:
            if _dim_layer is None or _dim_layer.get_size() != logical_surface.get_size():
                _dim_layer = pygame.Surface(logical_surface.get_size())
                _dim_layer.fill((0, 0, 0))
            _dim_layer.set_alpha(veil)
            logical_surface.blit(_dim_layer, (0, 0))

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
