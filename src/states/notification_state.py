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


    def draw_pomodoro(self, surface, time_left, mode):
        import pygame
        # Minimalist notification theme
        mins = int(time_left) // 60
        secs = int(time_left) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        
        font = pygame.font.Font(None, 24)
        
        bg_rect = pygame.Rect(0, 0, surface.get_width(), 20)
        c = (200, 40, 40) if mode == 'work' else (40, 180, 80)
        
        pygame.draw.rect(surface, c, bg_rect)
        
        overlay_surf = font.render(time_str, True, (255, 255, 255))
        surface.blit(overlay_surf, overlay_surf.get_rect(center=bg_rect.center))
