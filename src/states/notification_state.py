import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, YELLOW_BG, BLACK
from states.base_state import State

class NotificationState(State):
    """Temporary alert state."""
    def __init__(self, state_manager):
        super().__init__(state_manager)
        self.font = pygame.font.Font(None, 36)
        self.timer = 0.0
        
    def enter(self):
        # Reset the timer every time we enter this state
        self.timer = 0.0
        
    def update(self, dt):
        self.timer += dt
        # After 3 seconds, return to ambient state
        if self.timer >= 3.0:
            self.manager.change_state('ambient')
            
    def draw(self, surface):
        surface.fill(YELLOW_BG)
        text_surface = self.font.render("Alert!", True, BLACK)
        text_rect = text_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        surface.blit(text_surface, text_rect)
