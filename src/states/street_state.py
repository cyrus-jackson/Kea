import pygame
from states.base_state import State

class StreetState(State):
    def __init__(self, state_manager):
        super().__init__(state_manager)
        
    def enter(self):
        print("Entering Street State")
        
    def exit(self):
        print("Exiting Street State")
        
    def handle_events(self, events):
        pass
        
    def update(self, dt):
        pass
        
    def draw(self, surface):
        # Placeholder styling for the street state
        surface.fill((30, 30, 40)) # Dark grayish blue
