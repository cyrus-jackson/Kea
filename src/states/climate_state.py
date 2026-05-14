import pygame
import random
from states.base_state import State
from backend.weather_api import fetch_stuttgart_weather
from ui.glow_text import GlowText
from config import SCREEN_WIDTH, SCREEN_HEIGHT
from current_affairs import CurrentAffairs

class ClimateState(State):
    def __init__(self, manager):
        super().__init__(manager)
        self.current_affairs = CurrentAffairs()
        self.weather_data = None
        self.loading = True
        
        # UI Elements: smaller text to emulate Divoom, centered left
        info_font = pygame.font.Font(None, 24)
        self.info_text = GlowText(info_font, "...", (255, 255, 255), (100, 100, 100))
        
        self.animation_timer = 0.0
        self.particles = []  # For rain or background effects

    def enter(self):
        self.loading = True
        self.particles = []
        self.info_text.update_text("FETCHING\nWEATHER...")
        fetch_stuttgart_weather(self._on_weather_fetched)

    def _on_weather_fetched(self, data):
        self.weather_data = data
        self.loading = False
        
        if data.get("error"):
            self.info_text.update_text("WEATHER\nERROR")
            return

        # Prepare UI info
        temp = data.get("temp", "?")
        rain_chance = data.get("rain_chance", 0)
        needs_umbrella = data.get("needs_umbrella", False)
        
        umbrella_txt = "UMBRELLA: YES" if needs_umbrella else "UMBRELLA: NO"
        self.info_text.update_text(f"STUTTGART: {temp}C \nRAIN: {rain_chance}%\n{umbrella_txt}")
        
        # We will parse columns dynamically in the draw function using a smaller font
        self.column_font = pygame.font.Font(None, 20)
        
        # Inject to Current Affairs
        status = f"RAIN {rain_chance}%" if rain_chance > 20 else "CLEAR"
        message = f"STUTTGART WEATHER UPDATE: {temp}C, {status}."
        if hasattr(self.current_affairs, 'add_important_message'):
            self.current_affairs.add_important_message(message)

        # Setup particles based on weather
        self._init_particles()

    def _init_particles(self):
        self.particles = []
        if self.weather_data and self.weather_data.get("needs_umbrella"):
            # Init rain drops
            for _ in range(50):
                x = random.randint(0, SCREEN_WIDTH)
                y = random.randint(0, SCREEN_HEIGHT)
                speed = random.uniform(200, 400)
                length = random.randint(10, 20)
                self.particles.append([x, y, speed, length])

    def update(self, dt):
        self.animation_timer += dt
        
        if self.weather_data and not self.loading and not self.weather_data.get("error"):
            if self.weather_data.get("needs_umbrella"):
                # Rain logic
                for p in self.particles:
                    p[1] += p[2] * dt
                    # Also slight wind to the right
                    p[0] += 50 * dt
                    if p[1] > SCREEN_HEIGHT:
                        p[1] = -p[3]
                        p[0] = random.randint(-50, SCREEN_WIDTH)

    def draw(self, surface):
        if self.weather_data and not self.loading and not self.weather_data.get("error"):
            # Change background based on time of day
            if self.weather_data.get("is_day"):
                surface.fill((80, 150, 220))  # Bright sky blue for day
            else:
                surface.fill((10, 15, 25))    # Dark background for night
        else:
            surface.fill((10, 15, 25)) # Default dark background
        
        if self.loading:
            pygame.draw.circle(surface, (100, 100, 100), (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2), 20, 2)
            pygame.draw.arc(surface, (255, 255, 255), 
                            (SCREEN_WIDTH//2 - 20, SCREEN_HEIGHT//2 - 20, 40, 40), 
                            self.animation_timer * 5, self.animation_timer * 5 + 2, 3)
            self.info_text.draw(surface, (20, SCREEN_HEIGHT - 80))
            return

        if self.weather_data and not self.weather_data.get("error"):
            # If it's day, always show the sun
            if self.weather_data.get("is_day"):
                center_y = int(SCREEN_HEIGHT * 0.4)
                center_x = SCREEN_WIDTH // 2
                
                # Draw Sun
                pygame.draw.circle(surface, (255, 204, 0), (center_x, center_y), 30)
                
                # Draw sun rays if not raining heavy
                import math
                num_rays = 8
                # Slow the rotation and reduce ray amplitude for a calmer sun
                ray_length = 12 + math.sin(self.animation_timer * 1.0) * 5
                for i in range(num_rays):
                    angle = self.animation_timer * 0.3 + (i * 2 * math.pi / num_rays)
                    start_x = center_x + math.cos(angle) * 35
                    start_y = center_y + math.sin(angle) * 35
                    end_x = center_x + math.cos(angle) * (35 + ray_length)
                    end_y = center_y + math.sin(angle) * (35 + ray_length)
                    pygame.draw.line(surface, (255, 204, 0), (start_x, start_y), (end_x, end_y), 4)

                # Determine Face Expression
                temp = self.weather_data.get("temp", 20)
                is_raining = self.weather_data.get("needs_umbrella", False)
                
                # Face colors
                eye_color = (50, 50, 50)
                
                # Eyes
                pygame.draw.circle(surface, eye_color, (center_x - 10, center_y - 5), 4)
                pygame.draw.circle(surface, eye_color, (center_x + 10, center_y - 5), 4)
                
                # Mouth
                if is_raining:
                    # Unhappy (frown)
                    pygame.draw.arc(surface, eye_color, (center_x - 12, center_y + 5, 24, 15), 0, math.pi, 2)
                elif temp > 28:
                    # Serious (straight line)
                    pygame.draw.line(surface, eye_color, (center_x - 10, center_y + 10), (center_x + 10, center_y + 10), 2)
                    # Add a slower, subtler sweat drop for hot sun
                    sweat_y = center_y - 15 + (self.animation_timer * 1.5) % 8
                    pygame.draw.ellipse(surface, (100, 200, 255), (center_x + 15, sweat_y, 6, 8))
                else:
                    # Smiling (pleasant)
                    pygame.draw.arc(surface, eye_color, (center_x - 12, center_y, 24, 15), math.pi, 2 * math.pi, 2)

            # Draw Rain Particles if needed
            if self.weather_data.get("needs_umbrella"):
                for p in self.particles:
                    pygame.draw.line(surface, (80, 120, 200), (int(p[0]), int(p[1])), 
                                     (int(p[0] + 5), int(p[1] + p[3])), 2)
            
            # Draw Columns (hourly forecast)
            columns = self.weather_data.get("forecast_columns", [])
            if columns and hasattr(self, 'column_font'):
                # Draw a dark translucent band for the forecast columns to ensure text legibility
                overlay = pygame.Surface((SCREEN_WIDTH, 80), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 100))
                surface.blit(overlay, (0, SCREEN_HEIGHT - 90))
                
                col_width = SCREEN_WIDTH // len(columns)
                for i, col in enumerate(columns):
                    x_offset = i * col_width + (col_width // 2)
                    y_start = SCREEN_HEIGHT - 60
                    
                    time_surf = self.column_font.render(col["hour"], True, (200, 200, 200))
                    temp_surf = self.column_font.render(f"{col['temp']}C", True, (255, 255, 255))
                    rain_surf = self.column_font.render(f"{col['precip']}%", True, (80, 150, 255))
                    
                    surface.blit(time_surf, time_surf.get_rect(center=(x_offset, y_start)))
                    surface.blit(temp_surf, temp_surf.get_rect(center=(x_offset, y_start + 20)))
                    surface.blit(rain_surf, rain_surf.get_rect(center=(x_offset, y_start + 40)))

        # Draw text at the top left to leave room at the bottom for columns
        self.info_text.draw(surface, (10, 10))
