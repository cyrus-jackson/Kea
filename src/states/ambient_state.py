import pygame
import random
import math
from config import SCREEN_WIDTH, SCREEN_HEIGHT, DARK_BLUE, WHITE
from states.base_state import State
from ui.glow_text import GlowText
from current_affairs import CurrentAffairs

class AmbientState(State):
    def __init__(self, state_manager):
        super().__init__(state_manager)

        self.city_h = int(SCREEN_HEIGHT * 0.75)
        self.water_h = SCREEN_HEIGHT - self.city_h
        
        # 1. Create separate surfaces for sky and layers to interleave dynamic traffic
        self.sky_surface = pygame.Surface((SCREEN_WIDTH, self.city_h), pygame.SRCALPHA)
        self.layer_surfaces = []
        
        self.roads = []
        # 2. Call our procedural generator to paint the layers
        self.generate_city()
        
        # 3. Dynamic Elements (Traffic)
        # Optimized counts for Raspberry Pi performance
        self.traffic = self.gen_traffic(num_cars=16, speed=20)
        self.traffic.extend(self.gen_sky_traffic(num_cars=2, speed=10))
        
        # 4. Timer for water reflection animation & scene reset
        self.reflection_timer = 0.0
        self.scene_reset_timer = 0.0
        self.scroll_x = 0.0

        # 4b. Celestial bodies (planets, moons) that rotate slowly
        self.celestial_bodies = self.generate_celestial_bodies()

        # 5. Weather variables (Configurable via set_weather)
        self.rain_intensity = 0.0 # 0.0 (off) to 1.0 (heavy storm)
        self.wind_speed = 0.0     # negative = left, positive = right
        self.raindrops = []
        self.water_ripples = []   # Ripples for the lake surface
        self.lightning_timer = random.uniform(5.0, 15.0)
        self.lightning_flash_alpha = 0.1
        
        # 6. Cached surfaces to avoid memory allocation every frame (Optimized for Raspberry Pi)
        # Lightning flash overlay in the sky area
        self.cached_flash_surf = pygame.Surface((SCREEN_WIDTH, self.city_h), pygame.SRCALPHA)

        # Weather overlay (rain + ripples)
        self.cached_weather_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        # Separate surface for rendering the city (sky + buildings + traffic)
        # This ensures we have a clean capture for the reflection without main.py's pre-fill clearing it
        self.city_render_surface = pygame.Surface((SCREEN_WIDTH, self.city_h), pygame.SRCALPHA)

        # Tint/darken overlay for reflection (applied after reflection blit)
        self.cached_reflection_darken_surf = pygame.Surface((SCREEN_WIDTH, self.water_h), pygame.SRCALPHA)
        self.cached_reflection_darken_surf.fill((0, 25, 60, 90))

        # Vertical fade so reflection disappears into darker water
        self.cached_reflection_fade = pygame.Surface((SCREEN_WIDTH, self.water_h), pygame.SRCALPHA)
        if self.water_h > 0:
            for y in range(self.water_h):
                t = 0.0 if self.water_h <= 1 else (y / (self.water_h - 1))
                a = int(235 * (1.0 - (t ** 1.5)))
                pygame.draw.line(self.cached_reflection_fade, (255, 255, 255, a), (0, y), (SCREEN_WIDTH, y))

        # 7. Glowing Text UI
        pygame.font.init()    

        # Current affairs feed (message service) + display GlowText (small font)
        self.current_affairs = CurrentAffairs()
        affairs_font = pygame.font.Font(None, 20)
        self.affairs_text = GlowText(affairs_font, self.current_affairs.get_current_message(), (255, 200, 120), (255, 120, 20), glow_radius=2, max_width=SCREEN_WIDTH - 80)

        # --- TO TEST THE WEATHER --- 
        # Uncomment the line below to test a full storm with lightning and heavy wind!
        self.set_weather(rain_intensity=0.01, wind_speed=-10.0)

    def set_weather(self, rain_intensity, wind_speed):
        """Can be called externally to configure weather."""
        self.rain_intensity = max(0.0, min(1.0, rain_intensity))
        self.wind_speed = wind_speed

    def get_hsv_color(self, h, s, v):
        """Helper to create a Pygame Color from HSV values."""
        c = pygame.Color(0, 0, 0)
        # Pygame uses H (0-360), S (0-100), V (0-100), A (0-100)
        c.hsva = (int(h) % 360, int(max(0, min(100, s))), int(max(0, min(100, v))), 100)
        return c

    def generate_celestial_bodies(self):
        """Generate dim background planets and a bright sun/moon orbital system."""
        bodies = []
        
        # Generate 2-3 DIM background planets (won't interfere with sun/moon)
        num_dim_planets = random.randint(2, 3)
        for _ in range(num_dim_planets):
            body = {
                'x': random.randint(50, SCREEN_WIDTH - 50),
                'y': random.randint(20, int(self.city_h * 0.4)),
                'radius': random.randint(6, 15),
                'color': self.get_hsv_color(random.randint(0, 360), random.randint(30, 80), random.randint(40, 60)),  # Dimmer
                'rotation': 0.0,
                'rotation_speed': random.uniform(0.05, 0.2),  # Slower rotation
                'has_rings': random.random() < 0.2,  # Fewer rings
                'ring_color': self.get_hsv_color(random.randint(0, 360), random.randint(40, 60), random.randint(40, 60)),
                'alpha': 120,  # DIM these background planets
            }
            bodies.append(body)
        
        # Create the SUN/MOON orbital system (bright and moves across sky)
        self.orbital_timer = 0.0
        self.sun_moon = {
            'radius': 20,
            'orbit_speed': 0.025,  # Complete orbit every ~7 seconds for testing (adjust as needed)
            'center_x': SCREEN_WIDTH / 2,
            'center_y': int(self.city_h * 0.35),
            'orbit_radius_x': SCREEN_WIDTH * 0.4,
            'orbit_radius_y': int(self.city_h * 0.25),
        }
        
        return bodies

    def gen_windows(self, surface, start_x, end_x, start_y, end_y, win_w, win_h, color1, color2):
        """Translates your Lua genWindows function."""
        building_width = end_x - start_x
        building_height = end_y - start_y

        # Number of windows. Using int() ensures we get whole numbers
        windows_in_row = int((building_width - 2) / win_w)
        windows_in_col = int((building_height - 2) / win_h)

        for iy in range(windows_in_col + 1):
            for ix in range(windows_in_row + 1):
                # Calculate window positions exactly like Lua
                w_start_x = start_x + 1 + (ix * win_w)
                w_start_y = start_y + 3 + (iy * win_h)
                w_end_x = w_start_x + win_w - 2
                w_end_y = w_start_y + win_h - 3

                if w_end_x < end_x:
                    draw_chance = random.randint(1, 10)
                    
                    if draw_chance >= 7:
                        # 75% chance for color1, 25% chance for color2
                        chosen_color = random.choice([color1, color1, color1, color2])
                        
                        # Convert Start/End coordinates to Pygame's Width/Height format
                        rect_w = w_end_x - w_start_x
                        rect_h = w_end_y - w_start_y
                        
                        # Draw the window rectangle
                        if rect_w > 0 and rect_h > 0:
                            pygame.draw.rect(surface, chosen_color, (w_start_x, w_start_y, rect_w, rect_h))

    def gen_buildings(self, surface, b_width, b_height, b_start_x, b_color, win_w, win_h, win_c1, win_c2):
        """Translates your Lua genBuildings function."""
        canvas_h = surface.get_height()
        
        # Loop to draw multiple buildings
        # Adjusted slightly from Lua to ensure it covers the screen horizontally
        num_buildings = int(SCREEN_WIDTH / b_width) + 2 
        
        for i in range(num_buildings):
            # Calculate positions with randomness
            start_x = (b_width * i) + random.randint(int(-b_width), int(b_width))
            start_y = b_height + random.randint(-15, 15)
            end_x = start_x + b_width + random.randint(-10, 10)
            end_y = canvas_h
            
            rect_w = end_x - start_x
            rect_h = end_y - start_y
            
            if rect_w > 0:
                # 1. Draw the main building block
                pygame.draw.rect(surface, b_color, (start_x, start_y, rect_w, rect_h))
                
                # Choose a feature to add
                chosen_feature = random.choice(["Box", "Dome", "Light", "Platform", "Pylon", "None"])

                if chosen_feature == "Box":
                    box_start_x = random.randint(int(start_x), int(start_x + (rect_w/2)))
                    box_start_y = random.randint(int(start_y - 5), int(start_y - 1))
                    box_end_x = random.randint(int(start_x + (rect_w/2)), int(end_x))
                    box_end_y = start_y
                    if box_end_x > box_start_x:
                        pygame.draw.rect(surface, b_color, (box_start_x, box_start_y, box_end_x - box_start_x, box_end_y - box_start_y))

                elif chosen_feature == "Dome":
                    dome_diameter_min = max(2, rect_w / 2)
                    dome_diameter_max = max(2, rect_w)
                    if dome_diameter_max >= dome_diameter_min:
                        dome_diameter = random.randint(int(dome_diameter_min), int(dome_diameter_max))
                        dome_radius = dome_diameter / 2
                        dome_start_x = int((start_x + (rect_w/2)) - dome_radius)
                        dome_start_y = random.randint(int(start_y - dome_radius), int(start_y - (dome_radius/2)))
                        pygame.draw.ellipse(surface, b_color, (dome_start_x, dome_start_y, int(dome_diameter), int(dome_diameter)))

                elif chosen_feature == "Light":
                    light_color = self.get_hsv_color(5, 60, 100)
                    pygame.draw.rect(surface, light_color, (int(start_x + 2), int(start_y - 1), 1, 1))
                    pygame.draw.rect(surface, light_color, (int(end_x - 1), int(start_y - 1), 1, 1))

                elif chosen_feature == "Platform":
                    pygame.draw.line(surface, b_color, (start_x, start_y - 2), (end_x, start_y - 2))
                    pygame.draw.rect(surface, b_color, (int(start_x + 3), int(start_y - 1), 1, 1))
                    pygame.draw.rect(surface, b_color, (int(end_x - 2), int(start_y - 1), 1, 1))

                elif chosen_feature == "Pylon":
                    pylon_position = random.randint(int(start_x), int(end_x))
                    pylon_height = random.randint(2, 6)
                    pygame.draw.line(surface, b_color, (pylon_position, start_y), (pylon_position, start_y - pylon_height))
                
                # 2. Add Windows
                # Randomize window sizes slightly, keeping them from hitting 0
                curr_win_w = max(2, random.randint(win_w - 1, win_w + 1))
                curr_win_h = max(3, random.randint(win_h - 1, win_h + 1))

                self.gen_windows(surface, start_x, end_x, start_y, end_y, 
                                 curr_win_w, curr_win_h, win_c1, win_c2)

    def generate_city(self):
        # Base colors (using 0-100 for Sat/Val instead of Lua's 0.0-1.0)
        base_hue = random.randint(0, 360)
        base_sat = random.randint(15, 40)
        base_val = random.randint(81, 100)
        
        self.sky_hue = base_hue
        self.sky_sat = base_sat
        self.sky_val = base_val
        
        base_color = self.get_hsv_color(base_hue, base_sat, base_val)

        # Make sky details transparent so we can draw changing color behind it
        self.sky_surface.fill((0, 0, 0, 0))
        surf_h = int(SCREEN_HEIGHT * 0.75)
        
        # Draw stars
        num_stars = random.randint(20, 40)
        for _ in range(num_stars):
            star_x = random.randint(0, SCREEN_WIDTH)
            star_y = random.randint(0, surf_h)
            # Random brush size 1 or 2 as in Lua
            star_size = random.choice([1, 2])
            pygame.draw.rect(self.sky_surface, WHITE, (star_x, star_y, star_size, star_size))

        # Draw sphere (moon/planet)
        sphere_x = random.randint(6, max(7, SCREEN_WIDTH - 6))
        # Place in the upper third of the sky surface
        sphere_y = random.randint(6, max(7, int(surf_h / 3)))
        sphere_diameter = random.randint(10, 40)
        pygame.draw.ellipse(self.sky_surface, WHITE, (sphere_x, sphere_y, sphere_diameter, sphere_diameter))

        # Layer 1 Buildings (Background)
        b_width_1 = SCREEN_WIDTH / 10
        layer_1 = pygame.Surface((SCREEN_WIDTH, surf_h), pygame.SRCALPHA)
        b_height_1 = surf_h - (surf_h * 0.67) # True canvas height representation
        b_color_1 = self.get_hsv_color(base_hue - random.randint(5, 10), 
                                       base_sat + random.randint(5, 10), 
                                       base_val - random.randint(6, 10))
        
        # Call the generator!
        self.gen_buildings(layer_1, b_width_1, b_height_1, 0, b_color_1, 
                           2, 4, base_color, base_color)
                           
        # Layer 1 Road
        road_min_1 = int(surf_h * 0.70)
        road_max_1 = int(surf_h * 0.75)
        road_thickness_1 = 2
        # Use the exact same color you generated for the buildings on this layer
        road_color_1 = b_color_1 
        road_y_1 = random.randint(road_min_1, road_max_1)
        self.roads.append({'y': road_y_1, 'thickness': road_thickness_1, 'layer': 0})

        # Call the road generator!
        self.gen_road(layer_1, road_y_1, road_thickness_1, road_color_1)
        self.layer_surfaces.append(layer_1)

        # Layer 2 Buildings
        b_width_2 = SCREEN_WIDTH / 9
        layer_2 = pygame.Surface((SCREEN_WIDTH, surf_h), pygame.SRCALPHA)
        b_height_2 = surf_h - (surf_h * 0.60)
        b_color_2 = self.get_hsv_color(base_hue - random.randint(10, 15), 
                                       base_sat + random.randint(5, 10), 
                                       base_val - random.randint(15, 25))
        
        self.gen_buildings(layer_2, b_width_2, b_height_2, 0, b_color_2, 
                           3, 5, base_color, b_color_1)
                           
        # Layer 2 Road
        road_min_2 = int(surf_h * 0.75)
        road_max_2 = int(surf_h * 0.80)
        road_thickness_2 = 3
        road_color_2 = b_color_2 
        road_y_2 = random.randint(road_min_2, road_max_2)
        self.roads.append({'y': road_y_2, 'thickness': road_thickness_2, 'layer': 1})

        self.gen_road(layer_2, road_y_2, road_thickness_2, road_color_2)
        self.layer_surfaces.append(layer_2)

        # Layer 3 Buildings
        layer_3 = pygame.Surface((SCREEN_WIDTH, surf_h), pygame.SRCALPHA)
        b_width_3 = SCREEN_WIDTH / 8
        b_height_3 = surf_h - (surf_h * 0.59)
        b_color_3 = self.get_hsv_color(base_hue - random.randint(15, 20), 
                                       base_sat + random.randint(5, 10), 
                                       base_val - random.randint(15, 25))
        
        self.gen_buildings(layer_3, b_width_3, b_height_3, 0, b_color_3, 
                           4, 6, b_color_1, b_color_2)
                           
        # Layer 3 Road
        road_min_3 = int(surf_h * 0.80)
        road_max_3 = int(surf_h * 0.85)
        road_thickness_3 = 3
        road_color_3 = b_color_3 
        road_y_3 = random.randint(road_min_3, road_max_3)
        self.roads.append({'y': road_y_3, 'thickness': road_thickness_3, 'layer': 2})

        self.gen_road(layer_3, road_y_3, road_thickness_3, road_color_3)
        self.layer_surfaces.append(layer_3)

        # Layer 4 Buildings
        layer_4 = pygame.Surface((SCREEN_WIDTH, surf_h), pygame.SRCALPHA)
        b_width_4 = SCREEN_WIDTH / 7
        b_height_4 = surf_h - (surf_h * 0.50)
        b_color_4 = self.get_hsv_color(base_hue - random.randint(20, 25), 
                                       base_sat + random.randint(5, 10), 
                                       base_val - random.randint(35, 55))
        
        self.gen_buildings(layer_4, b_width_4, b_height_4, 0, b_color_4, 
                           5, 7, b_color_2, b_color_3)
                           
        # Layer 4 Road
        road_min_4 = int(surf_h * 0.85)
        road_max_4 = int(surf_h * 0.90)
        road_thickness_4 = 4
        road_color_4 = b_color_4 
        road_y_4 = random.randint(road_min_4, road_max_4)
        self.roads.append({'y': road_y_4, 'thickness': road_thickness_4, 'layer': 3})

        self.gen_road(layer_4, road_y_4, road_thickness_4, road_color_4)
        self.layer_surfaces.append(layer_4)

        # Layer 5 Buildings
        layer_5 = pygame.Surface((SCREEN_WIDTH, surf_h), pygame.SRCALPHA)
        b_width_5 = SCREEN_WIDTH / 6
        b_height_5 = surf_h - (surf_h * 0.48)
        b_color_5 = self.get_hsv_color(base_hue - random.randint(30, 45), 
                                       base_sat + random.randint(5, 10), 
                                       base_val - random.randint(55, 70))
        
        self.gen_buildings(layer_5, b_width_5, b_height_5, 0, b_color_5, 
                           6, 8, b_color_3, b_color_4)
                           
        # Layer 5 Road
        road_min_5 = int(surf_h * 0.90)
        road_max_5 = int(surf_h * 0.95)
        road_thickness_5 = 6
        road_color_5 = b_color_5 
        road_y_5 = random.randint(road_min_5, road_max_5)
        self.roads.append({'y': road_y_5, 'thickness': road_thickness_5, 'layer': 4})

        self.gen_road(layer_5, road_y_5, road_thickness_5, road_color_5)
        self.layer_surfaces.append(layer_5)

        # Layer 6 Buildings
        layer_6 = pygame.Surface((SCREEN_WIDTH, surf_h), pygame.SRCALPHA)
        b_width_6 = SCREEN_WIDTH / 5
        b_height_6 = surf_h - (surf_h * 0.42)
        b_color_6 = self.get_hsv_color(base_hue - random.randint(50, 70), 
                                       base_sat + random.randint(5, 10), 
                                       base_val - random.randint(70, 80))
        
        self.gen_buildings(layer_6, b_width_6, b_height_6, 0, b_color_6, 
                           7, 9, b_color_5, b_color_6)
                           
        # Layer 6 Road
        road_min_6 = int(surf_h * 0.95)
        road_max_6 = surf_h - 8
        road_thickness_6 = 8
        road_color_6 = b_color_6 
        road_y_6 = random.randint(road_min_6, road_max_6)
        self.roads.append({'y': road_y_6, 'thickness': road_thickness_6, 'layer': 5})

        self.gen_road(layer_6, road_y_6, road_thickness_6, road_color_6)
        self.layer_surfaces.append(layer_6)

    def gen_traffic(self, num_cars, speed):
        """Translate your Lua genTraffic() here."""
        cars = []
        for _ in range(num_cars):
            # Select a random road for the car to drive on
            road = random.choice(self.roads) if hasattr(self, 'roads') and self.roads else {'y': int(SCREEN_HEIGHT * 0.50), 'thickness': 2, 'layer': 0}
            # The car is 2 pixels tall, so keep it within the road thickness
            car_h = 2
            car_y = road['y'] + random.randint(0, max(0, road['thickness'] - car_h))
            
            cars.append({
                'x': random.uniform(0, SCREEN_WIDTH),
                'y': car_y,
                'speed': speed * random.uniform(0.8, 1.2) * random.choice([1, -1]), # Randomize direction and slightly randomize speed
                'layer': road.get('layer', 0)
            })
        return cars
    
    def gen_sky_traffic(self, num_cars, speed):
        """Generates Star Wars style flying vehicles."""
        cars = []
        surf_h = int(SCREEN_HEIGHT * 0.95)
        for _ in range(num_cars):
            cars.append({
                'x': random.uniform(0, SCREEN_WIDTH),
                'y': random.uniform(surf_h * 0.1, surf_h * 0.75),
                'speed': speed * random.uniform(1.5, 4.0) * random.choice([1, -1]),
                'layer': random.randint(0, 5),
                'is_sky': True,
                'trail': random.randint(4, 15),
                'color': random.choice([(255, 100, 100), (100, 255, 255), (100, 255, 100), (255, 255, 255)])
            })
        return cars

    def gen_road(self, surface, road_y, road_thickness, road_color):
        """Translates your Lua genRoad function."""
        canvas_w = surface.get_width()
        canvas_h = surface.get_height()

        # 1. Base Road Rectangle
        pygame.draw.rect(surface, road_color, (0, road_y, canvas_w, road_thickness))

        # 2. Draw Struts
        # int() ensures we don't pass decimal pixels to Pygame
        # max(1, ...) ensures we never accidentally divide by zero if thickness is 0
        num_struts = int(canvas_w / max(1, road_thickness))
        strut_w = max(1, int((road_thickness / 3) * 2)) 
        strut_interval = strut_w * 5

        for i in range(num_struts + 1):
            strut_x = int(i * strut_interval + (i * strut_w))
            
            # Draw strut going down to the bottom of the canvas
            pygame.draw.rect(surface, road_color, (strut_x, road_y, strut_w, canvas_h - road_y))

            # Draw arches (using pygame.draw.line)
            # Syntax: (surface, color, start_pos, end_pos)
            arch_y = road_y + road_thickness + 1
            pygame.draw.line(surface, road_color, 
                             (strut_x - 2, arch_y), 
                             (strut_x + strut_w + 2, arch_y))

        # 3. Draw Railing (50% chance)
        if random.randint(0, 1) > 0:
            railing_y = int(road_y - road_thickness / 2)
            
            # Top rail
            pygame.draw.line(surface, road_color, (0, railing_y), (canvas_w, railing_y))

            num_poles = int(canvas_w / 2)
            pole_w = 1
            pole_interval = 2
            pole_start = random.randint(-10, 10)

            # Loop to draw railing poles
            for i in range(num_poles + 1):
                pole_x = pole_start + i * pole_interval + (i * pole_w)
                pygame.draw.rect(surface, road_color, (pole_x, railing_y, pole_w, road_y - railing_y))

        # 4. Draw Streetlamps
        num_lamps = int(canvas_w / 4)
        lamp_w = 1
        lamp_h = 8
        lamp_interval = 24
        lamp_start = random.randint(-10, 10)
        
        # Creating a warm, bright light color (Hue 45, low saturation, max brightness)
        light_color = self.get_hsv_color(45, 10, 100)

        for i in range(num_lamps + 1):
            lamp_x = lamp_start + i * lamp_interval + (i * lamp_w)

            # Draw Post
            pygame.draw.rect(surface, road_color, (lamp_x, road_y - lamp_h, lamp_w, lamp_h))
            
            # Draw Head (slightly wider)
            pygame.draw.rect(surface, road_color, (lamp_x, road_y - lamp_h, lamp_w + 2, 2))
            
            # Draw Light (Using a 2x2 rect instead of pencil tool)
            pygame.draw.rect(surface, light_color, (lamp_x + 3, road_y - lamp_h + 2, 2, 2))

    def update(self, dt):
        """All animation math happens here."""
        # Scroll the background (parallax)
        self.scroll_x += dt * 0.0

        # Move traffic
        for car in self.traffic:
            car['x'] += car['speed'] * dt
            
            respawn = False
            if car['x'] > SCREEN_WIDTH + 20:
                car['x'] = -20 # Reset offscreen on left
                respawn = True
            elif car['x'] < -20:
                car['x'] = SCREEN_WIDTH + 20 # Reset offscreen on right
                respawn = True
                
            if respawn:
                if car.get('is_sky'):
                    surf_h = int(SCREEN_HEIGHT * 0.75)
                    car['y'] = random.uniform(surf_h * 0.1, surf_h * 0.75)
                    car['layer'] = random.randint(0, 5)
                    car['trail'] = random.randint(4, 15)
                    car['color'] = random.choice([(255, 100, 100), (100, 255, 255), (100, 255, 100), (255, 255, 255)])
                    # Keep same direction but randomize speed
                    dir_mod = 1 if car['speed'] > 0 else -1
                    car['speed'] = 40 * random.uniform(1.5, 4.0) * dir_mod
                else:
                    road = random.choice(self.roads) if hasattr(self, 'roads') and self.roads else {'y': int(SCREEN_HEIGHT * 0.50), 'thickness': 2, 'layer': 0}
                    car_h = 2
                    car['y'] = road['y'] + random.randint(0, max(0, road['thickness'] - car_h))
                    car['layer'] = road.get('layer', 0)
                    dir_mod = 1 if car['speed'] > 0 else -1
                    car['speed'] = 20 * random.uniform(0.8, 1.2) * dir_mod

        self.reflection_timer += dt * 3.0

        # Periodically reset the entire city to get new fresh colors for buildings and sky
        self.scene_reset_timer += dt
        if self.scene_reset_timer >= 60.0:
            self.scene_reset_timer = 0.0
            self.generate_city()

        # --- Update Weather ---
        # Generate new raindrops according to intensity
        target_drops = int(self.rain_intensity * 400) # Max 400 drops
        while len(self.raindrops) < target_drops:
            self.raindrops.append({
                'x': random.uniform(0, SCREEN_WIDTH),
                'y': random.uniform(-SCREEN_HEIGHT, 0),
                'speed': random.uniform(300, 500) + (self.rain_intensity * 200),
                'length': random.uniform(10, 20) + (self.rain_intensity * 10)
            })
        while len(self.raindrops) > target_drops:
            self.raindrops.pop()
            
        # Move raindrops
        for drop in self.raindrops:
            drop['x'] += self.wind_speed * dt
            drop['y'] += drop['speed'] * dt
            
            # Wrap drops around the screen
            if drop['y'] > SCREEN_HEIGHT:
                # Optimized Ripple Spawning: Only spawn sometimes to save performance on Pi
                if random.random() < 0.45: 
                    self.water_ripples.append({
                        'x': drop['x'],
                        'y': random.uniform(SCREEN_HEIGHT * 0.75, SCREEN_HEIGHT),
                        'life': 0.0,
                        'max_life': random.uniform(0.15, 0.3)
                    })
                    
                drop['y'] = random.uniform(-50, 0)
                if self.wind_speed < 0:
                    drop['x'] = random.uniform(0, SCREEN_WIDTH + abs(self.wind_speed))
                elif self.wind_speed > 0:
                    drop['x'] = random.uniform(-self.wind_speed, SCREEN_WIDTH)
                else:
                    drop['x'] = random.uniform(0, SCREEN_WIDTH)

        # Update Ripples
        for r in self.water_ripples:
            r['life'] += dt
        self.water_ripples = [r for r in self.water_ripples if r['life'] < r['max_life']]

        # Update celestial bodies (slow rotation)
        for body in self.celestial_bodies:
            body['rotation'] += body['rotation_speed'] * dt
        
        # Update sun/moon orbital position
        self.orbital_timer += dt * self.sun_moon['orbit_speed']
        # Use sine wave for elliptical orbit
        sun_x = self.sun_moon['center_x'] + math.cos(self.orbital_timer) * self.sun_moon['orbit_radius_x']
        sun_y = self.sun_moon['center_y'] + math.sin(self.orbital_timer) * self.sun_moon['orbit_radius_y']
        self.sun_moon['x'] = sun_x
        self.sun_moon['y'] = sun_y

        # Lightning logic (only happens at very high rain intensities)
        if self.rain_intensity >= 0.8:
            self.lightning_timer -= dt
            if self.lightning_timer <= 0:
                self.lightning_flash_alpha = 255.0 # Max flash brightness
                self.lightning_timer = random.uniform(1.0, 5.0) # Time until next lightning strike
        else:
            self.lightning_timer = random.uniform(5.0, 15.0)
            
        # Fade out lightning flash quickly
        if self.lightning_flash_alpha > 0:
            self.lightning_flash_alpha -= 900 * dt
            if self.lightning_flash_alpha < 0:
                self.lightning_flash_alpha = 0

        # Update CurrentAffairs and refresh displayed text when it changes
        if hasattr(self, 'current_affairs'):
            changed = self.current_affairs.update(dt)
            if changed:
                self.affairs_text.update_text(self.current_affairs.get_current_message())

    def draw(self, surface):
        """Render everything to the main screen."""
        city_h = self.city_h
        water_h = self.water_h

        # --- STEP 1: Render the city to a separate surface ---
        # This ensures reflection can capture it cleanly (main.py fills surface with black before calling draw)
        self.city_render_surface.fill((0, 0, 0, 0))  # Clear the city surface
        
        # 1. Draw the changing sky background color
        sky_bg_color = self.get_hsv_color(self.sky_hue, self.sky_sat, self.sky_val)
        pygame.draw.rect(self.city_render_surface, sky_bg_color, (0, 0, SCREEN_WIDTH, city_h))
        
        # Draw the static sky details (stars, moon)
        self.city_render_surface.blit(self.sky_surface, (0, 0))
        
        # Draw rotating celestial bodies (DIM background planets)
        for body in self.celestial_bodies:
            x, y, radius = int(body['x']), int(body['y']), body['radius']
            color = body['color']
            
            # Create a temporary surface with alpha for dim planets
            dim_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            
            # Draw main planet/moon on temp surface
            pygame.draw.circle(dim_surf, (*color[:3], body.get('alpha', 120)), (radius + 2, radius + 2), radius)
            
            # Add subtle shading/highlight
            pygame.draw.circle(dim_surf, (255, 255, 255, 40), (radius - radius // 3 + 2, radius - radius // 3 + 2), radius // 4)
            
            # Draw rings if this body has them
            if body['has_rings']:
                ring_color = body['ring_color']
                tilt = math.cos(math.radians(body['rotation'])) * 0.5
                ring_w = int(radius * 2.5)
                ring_h = int(radius * 0.8 * (1.0 - abs(tilt)))
                
                if ring_h > 0:
                    pygame.draw.ellipse(dim_surf, (*ring_color[:3], body.get('alpha', 120)), 
                                       (2 + radius - ring_w // 2, 2 + radius - ring_h // 2, ring_w, ring_h), 2)
            
            # Blit the dim planet to the city surface
            self.city_render_surface.blit(dim_surf, (x - radius - 2, y - radius - 2))
        
        # Draw bright SUN/MOON (stays bright, orbits across sky)
        sun_x = int(self.sun_moon['x'])
        sun_y = int(self.sun_moon['y'])
        sun_radius = self.sun_moon['radius']
        sun_color = (255, 220, 100)  # Warm yellow-white
        
        # Draw sun glow (multiple circles with decreasing alpha for radial glow effect)
        glow_layers = [
            (60, 255, 200, 150, 80),   # radius, R, G, B, alpha
            (50, 255, 210, 120, 100),
            (40, 255, 230, 100, 60),
            (30, 255, 240, 150, 40),
        ]
        for glow_radius, r, g, b, alpha in glow_layers:
            glow_surf = pygame.Surface((glow_radius * 2 + 4, glow_radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (r, g, b, alpha), (glow_radius + 2, glow_radius + 2), glow_radius)
            self.city_render_surface.blit(glow_surf, (sun_x - glow_radius - 2, sun_y - glow_radius - 2))
        
        # Draw light rays emanating from sun (downward and outward)
        # Rays are more visible when sun is higher in the sky
        sun_center_y = self.sun_moon['center_y']
        sun_height = sun_center_y - sun_y  # Positive when sun is above center
        ray_visibility = max(0.1, min(1.0, sun_height / sun_center_y))  # Fade when sun sets
        
        if ray_visibility > 0.2:
            num_rays = 12
            ray_surf = pygame.Surface((SCREEN_WIDTH, self.city_h), pygame.SRCALPHA)
            
            for i in range(num_rays):
                angle = (i / num_rays) * 2 * math.pi
                # Bias rays to point downward and outward from sun
                ray_angle = angle - math.pi / 2 + math.sin(angle) * 0.3
                
                # Ray length and opacity based on sun height
                ray_length = 100 + sun_height * 0.5
                ray_opacity = int(120 * ray_visibility)
                
                # Calculate ray endpoint
                ray_end_x = sun_x + math.cos(ray_angle) * ray_length
                ray_end_y = sun_y + math.sin(ray_angle) * ray_length
                
                # Draw ray with fade effect (thicker near sun, thinner at end)
                pygame.draw.line(ray_surf, (255, 240, 150, ray_opacity), 
                                (sun_x, sun_y), (int(ray_end_x), int(ray_end_y)), 3)
                pygame.draw.line(ray_surf, (255, 250, 200, ray_opacity // 2), 
                                (sun_x, sun_y), (int(ray_end_x), int(ray_end_y)), 1)
            
            self.city_render_surface.blit(ray_surf, (0, 0))
        
        # Draw the bright sun core
        pygame.draw.circle(self.city_render_surface, sun_color, (sun_x, sun_y), sun_radius)
        
        # Add bright highlight to sun
        pygame.draw.circle(self.city_render_surface, (255, 255, 200), (sun_x - sun_radius // 3, sun_y - sun_radius // 3), sun_radius // 3)
        
        # --- Lightning Flash in the Sky ---
        if self.lightning_flash_alpha > 0:
            self.cached_flash_surf.fill((255, 255, 255, int(min(255, max(0, self.lightning_flash_alpha)))))
            self.city_render_surface.blit(self.cached_flash_surf, (0, 0))
        
        # 2. Draw each layer of buildings and its traffic on top
        for i, layer_surf in enumerate(self.layer_surfaces):
            # Parallax scroll: foreground layers move faster
            parallax_factor = 0.1 + (i * 0.15)
            layer_offset_x = int(self.scroll_x * parallax_factor) % SCREEN_WIDTH
            
            # Blit twice to seamlessly wrap horizontally
            self.city_render_surface.blit(layer_surf, (-layer_offset_x, 0))
            self.city_render_surface.blit(layer_surf, (-layer_offset_x + SCREEN_WIDTH, 0))
            
            for car in self.traffic:
                if car.get('layer', 0) == i:
                    if car.get('is_sky'):
                        dir_mod = 1 if car['speed'] < 0 else -1
                        end_x = int(car['x'])
                        
                        # Simple colored trail
                        start_x = end_x + int(car.get('trail', 5) * dir_mod)
                        pygame.draw.line(self.city_render_surface, car.get('color', WHITE), (start_x, int(car['y'])), (end_x, int(car['y'])), 1)
                        
                        # Engine/ship dot
                        pygame.draw.rect(self.city_render_surface, WHITE, (end_x - (1 if dir_mod > 0 else 0), int(car['y']) - 1, 2, 2))
                    else:
                        pygame.draw.rect(self.city_render_surface, WHITE, (int(car['x']), car['y'], 4, 2))

        # --- STEP 2: Now blit the city to the main surface ---
        surface.blit(self.city_render_surface, (0, 0))

        # --- STEP 3: Draw the water + reflection ---
        if water_h > 0:
            # Base water color
            surface.fill(DARK_BLUE, pygame.Rect(0, city_h, SCREEN_WIDTH, water_h))

            # Capture the city we just rendered for reflection
            capture_src_y = int(city_h * 0.22)
            capture_h = max(1, city_h - capture_src_y)
            capture_rect = pygame.Rect(0, capture_src_y, SCREEN_WIDTH, capture_h)
            
            # Get the subsurface from city_render_surface (not the main surface which has been filled)
            try:
                reflection_src = self.city_render_surface.subsurface(capture_rect)
                flipped = pygame.transform.flip(reflection_src, False, True)
                reflection = pygame.transform.smoothscale(flipped, (SCREEN_WIDTH, water_h))

                # Make reflection clearly visible, then fade with depth
                reflection.set_alpha(215)
                reflection.blit(self.cached_reflection_fade, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

                # Wave distortion: blit horizontal slices with a small x offset
                # Optimized for Raspberry Pi performance (fewer blit calls)
                slice_h = 8
                for y in range(0, water_h, slice_h):
                    h = min(slice_h, water_h - y)
                    wave = math.sin(self.reflection_timer + y * 0.11)
                    amp = 1.2 + (y * 0.03)
                    offset_x = int(wave * amp)
                    surface.blit(reflection, (offset_x, city_h + y), area=pygame.Rect(0, y, SCREEN_WIDTH, h))

                # Tint/darken so it reads as water
                surface.blit(self.cached_reflection_darken_surf, (0, city_h))
            except ValueError:
                # If subsurface fails, just fill with solid water color
                pass

        # 4. Draw Weather overlay (Rain)
        if self.rain_intensity > 0:
            self.cached_weather_surf.fill((0, 0, 0, 0)) # Clear the transparent surface
            
            # Draw rain lines
            rain_color = (200, 200, 230, 150)
            wind_x_offset = self.wind_speed * 0.05 # Determine rain angle lag
            
            for drop in self.raindrops:
                start_pos = (drop['x'], drop['y'])
                end_pos = (drop['x'] - wind_x_offset, drop['y'] - drop['length'])
                pygame.draw.line(self.cached_weather_surf, rain_color, start_pos, end_pos, 1)

            # Draw high-performance droplets/ripples on the lake surface
            for ripple in self.water_ripples:
                prog = ripple['life'] / ripple['max_life']
                # Calculate ripple width relative to its life
                w = int(4 + (12 * prog)) 
                r_color = (200, 200, 230, int(150 * (1.0 - prog))) # Fades out
                
                pygame.draw.line(self.cached_weather_surf, r_color, 
                                 (ripple['x'] - w/2, ripple['y']), 
                                 (ripple['x'] + w/2, ripple['y']), 1)
            
            surface.blit(self.cached_weather_surf, (0, 0))


        # Draw current affairs at bottom-center
        if hasattr(self, 'affairs_text'):
            affairs_surf = self.affairs_text.get_surface()
            ax = (SCREEN_WIDTH - affairs_surf.get_width()) // 2
            ay = SCREEN_HEIGHT - affairs_surf.get_height() - 20
            self.affairs_text.draw(surface, (ax, ay))

    def draw_pomodoro(self, surface, time_left, mode):
        import pygame
        # Cyberpunk neon ambient theme timer
        mins = int(time_left) // 60
        secs = int(time_left) % 60
        time_str = f"{mins:02d}:{secs:02d}"
        
        from ui.glow_text import GlowText
        font = pygame.font.Font(None, 72)
        
        glow_c = (255, 50, 100) if mode == 'work' else (50, 255, 100)
        t = getattr(self, '_pomo_text', None)
        if not t or (t.text != time_str) or (t.glow_color != glow_c):
            self._pomo_text = GlowText(font, time_str, (255, 255, 255), glow_c, 5)
            
        surf = self._pomo_text.get_surface()
        # Center placement for cyberpunk
        x = (surface.get_width() - surf.get_width()) // 2
        y = (surface.get_height() - surf.get_height()) // 2
        surface.blit(surf, (x, y))
