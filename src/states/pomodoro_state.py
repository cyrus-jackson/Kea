import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, CRIMSON, WHITE
from states.base_state import State

class PomodoroState(State):
    """Timer state. Placeholder for a Pomodoro timer."""
    def __init__(self, state_manager):
        super().__init__(state_manager)
        # We need a font. None means default pygame font, size 36
        self.font = pygame.font.Font(None, 36)
        
    def draw(self, surface):
        surface.fill(CRIMSON)
        # Render the text
        text_surface = self.font.render("25:00", True, WHITE)
        # Get the rectangle of the text and center it
        text_rect = text_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        surface.blit(text_surface, text_rect)
