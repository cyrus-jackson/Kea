import pygame
import math
from config import SCREEN_WIDTH, SCREEN_HEIGHT, CRIMSON, WHITE
from states.base_state import State
from hardware_input import BUTTON_POMODORO_EVENT, BUTTON_NOTIFICATION_EVENT
from ui.glow_text import GlowText

WORK_TIME = 20 * 60
BREAK_TIME = 6 * 60

class PomodoroState(State):
    """Pomodoro timer styled with a futuristic, pulsing aesthetic."""
    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()
        self.font = pygame.font.Font(None, 72)
        self.small_font = pygame.font.Font(None, 24)
        
        self.mode = 'work'
        self.time_left = WORK_TIME
        self.running = False
        
        self.t = 0.0
        
        # We start with some default colors, they get updated in update()
        self.time_glow = GlowText(self.font, "20:00", WHITE, (255, 100, 100), 5)
        self.mode_glow = GlowText(self.small_font, "WORK MODE", WHITE, (255, 100, 100), 2)

    def enter(self):
        pass

    def handle_events(self, events):
        for event in events:
            if event.type == BUTTON_NOTIFICATION_EVENT:
                self.running = not self.running
            elif event.type == BUTTON_POMODORO_EVENT:
                # Reset time
                if self.mode == 'work':
                    self.time_left = WORK_TIME
                else:
                    self.time_left = BREAK_TIME
                self.running = False

    def update(self, dt):
        self.t += dt
        
        if self.running:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self.running = False
                if self.mode == 'work':
                    self.mode = 'break'
                    self.time_left = BREAK_TIME
                else:
                    self.mode = 'work'
                    self.time_left = WORK_TIME
                    
        # Update glowing text surfaces
        mins = int(self.time_left) // 60
        secs = int(self.time_left) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        
        # Set dynamic theme color
        glow_color = (255, 60, 60) if self.mode == 'work' else (60, 255, 120)
        self.time_glow.glow_color = glow_color
        self.mode_glow.glow_color = glow_color
        
        self.time_glow.update_text(time_str)
        self.mode_glow.update_text("WORK" if self.mode == 'work' else "BREAK")

    def draw(self, surface):
        surface.fill((10, 10, 15))  # Dark sleek background
        
        # Grid lines
        for x in range(0, SCREEN_WIDTH, 20):
            pygame.draw.line(surface, (20, 20, 30), (x, 0), (x, SCREEN_HEIGHT))
        for y in range(0, SCREEN_HEIGHT, 20):
            pygame.draw.line(surface, (20, 20, 30), (0, y), (SCREEN_WIDTH, y))
            
        # Draw circular progress rings
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        max_time = WORK_TIME if self.mode == 'work' else BREAK_TIME
        progress = self.time_left / max_time
        
        base_color = (255, 50, 50) if self.mode == 'work' else (50, 255, 120)
        ring_color = tuple(int(c * (0.6 + 0.4 * math.sin(self.t * 3))) for c in base_color) if self.running else base_color
        
        # Track ring
        pygame.draw.circle(surface, (30, 30, 40), (cx, cy), 90, 4)
        
        # Progress arc
        start_angle = -math.pi / 2
        end_angle = start_angle + (progress * 2 * math.pi)
        
        if progress > 0:
            points = []
            steps = 50
            for i in range(steps + 1):
                angle = start_angle + (end_angle - start_angle) * (i / steps)
                px = cx + math.cos(angle) * 90
                py = cy + math.sin(angle) * 90
                points.append((px, py))
            if len(points) > 1:
                pygame.draw.lines(surface, ring_color, False, points, 6)

        # Draw text centered
        time_surf = self.time_glow.get_surface()
        time_pos = (cx - time_surf.get_width() // 2, cy - time_surf.get_height() // 2 + 10)
        surface.blit(time_surf, time_pos)
        
        mode_surf = self.mode_glow.get_surface()
        mode_pos = (cx - mode_surf.get_width() // 2, cy - 60)
        surface.blit(mode_surf, mode_pos)

    def draw_overlay(self, surface):
        if not self.running:
            return
            
        mins = int(self.time_left) // 60
        secs = int(self.time_left) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        
        overlay_surf = self.small_font.render(time_str, True, WHITE)
        bg_rect = overlay_surf.get_rect(topright=(SCREEN_WIDTH - 5, 5))
        bg_rect.inflate_ip(10, 6)
        
        bg_color = (150, 0, 0, 180) if self.mode == 'work' else (40, 160, 80, 180)
        shape_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        shape_surf.fill(bg_color)
        
        surface.blit(shape_surf, bg_rect.topleft)
        surface.blit(overlay_surf, overlay_surf.get_rect(center=bg_rect.center))
