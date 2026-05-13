import pygame

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False
    print("WARNING: RPi.GPIO not found. Hardware buttons will not be active.")

# Define custom pygame events for each button action
BUTTON_AMBIENT_EVENT = pygame.USEREVENT + 1
BUTTON_POMODORO_EVENT = pygame.USEREVENT + 2
BUTTON_NOTIFICATION_EVENT = pygame.USEREVENT + 3

# Mapping: BCM Pin -> (Pygame Event, Button Description)
BUTTON_CONFIG = {
    21: (BUTTON_AMBIENT_EVENT, "Blue (Ambient)"),
    20: (BUTTON_POMODORO_EVENT, "Red (Pomodoro)"),
    26: (BUTTON_NOTIFICATION_EVENT, "Green (Notification)"),
}

class HardwareButtons:
    def __init__(self):
        self.previous_states = {}
        if not HAS_GPIO:
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        
        for pin, (event_type, desc) in BUTTON_CONFIG.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.previous_states[pin] = GPIO.HIGH
            
    def update(self):
        """Poll the buttons and post pygame events if pressed."""
        if not HAS_GPIO:
            return

        for pin, (event_type, desc) in BUTTON_CONFIG.items():
            current_state = GPIO.input(pin)
            
            # Button is pressed when state changes from HIGH to LOW
            if current_state == GPIO.LOW and self.previous_states[pin] == GPIO.HIGH:
                print(f"Hardware button pressed: {desc}")
                # Post the custom event to Pygame's event queue
                pygame.event.post(pygame.event.Event(event_type))
                
            self.previous_states[pin] = current_state

    def cleanup(self):
        """Clean up GPIO resources."""
        if HAS_GPIO:
            GPIO.cleanup()
