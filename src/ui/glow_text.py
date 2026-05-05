import pygame

class GlowText:
    def __init__(self, font, text, color, glow_color, glow_radius=2, max_width=None):
        """
        Initializes a reusable GlowText object.
        :param font: pygame.font.Font object to render with.
        :param text: String to display.
        :param color: The bright inner color of the text.
        :param glow_color: The color of the outer glow.
        :param glow_radius: How thick the glow should be.
        :param max_width: Maximum width in pixels before text wraps to a new line.
        """
        self.font = font
        self.text = text
        self.color = color
        self.glow_color = glow_color
        self.glow_radius = glow_radius
        self.max_width = max_width
        
        self._surface = self._pre_render()
        
    def _wrap_text(self, text):
        if not self.max_width:
            # Also support manual newlines
            return text.split('\n')
            
        words = text.split(' ')
        lines = []
        current_line = []
        current_width = 0
        
        # Space width
        space_width = self.font.render(' ', True, (0,0,0)).get_width()
        
        for word in words:
            word_width = self.font.render(word, True, (0,0,0)).get_width()
            
            if current_line and current_width + word_width > self.max_width:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_width = word_width + space_width
            else:
                current_line.append(word)
                current_width += word_width + space_width
                
        if current_line:
            lines.append(' '.join(current_line))
            
        return lines

    def _pre_render(self):
        """Renders the glowing text onto a single surface to optimize performance."""
        lines = self._wrap_text(self.text)
        
        # Render all lines for base and glow
        base_line_surfs = []
        glow_line_surfs = []
        max_base_width = 0
        total_base_height = 0
        
        for line in lines:
            line_base = self.font.render(line, True, self.color)
            line_glow = self.font.render(line, True, self.glow_color)
            
            base_line_surfs.append(line_base)
            glow_line_surfs.append(line_glow)
            
            max_base_width = max(max_base_width, line_base.get_width())
            total_base_height += line_base.get_height()
            
        # Create surfaces for the combined text block
        base_surface = pygame.Surface((max_base_width, total_base_height), pygame.SRCALPHA)
        glow_base_surface = pygame.Surface((max_base_width, total_base_height), pygame.SRCALPHA)
        
        current_y = 0
        for i in range(len(lines)):
            b_surf = base_line_surfs[i]
            g_surf = glow_line_surfs[i]
            # Center align text lines
            x_offset = (max_base_width - b_surf.get_width()) // 2
            
            base_surface.blit(b_surf, (x_offset, current_y))
            glow_base_surface.blit(g_surf, (x_offset, current_y))
            
            current_y += b_surf.get_height()

        width, height = max_base_width, total_base_height
        
        # Create a surface large enough to hold the text + glow
        padding = self.glow_radius * 2
        bounding_rect = pygame.Rect(0, 0, width + padding * 2, height + padding * 2)
        glow_surface = pygame.Surface(bounding_rect.size, pygame.SRCALPHA)
        
        # Render the glow (brute-force blur by drawing multiple times with low alpha)
        glow_alpha = max(10, 255 // (self.glow_radius ** 2 + 1))
        glow_base_surface.set_alpha(glow_alpha)
        
        center_x = padding
        center_y = padding
        
        # Draw text around the center in a circle
        for dx in range(-self.glow_radius, self.glow_radius + 1):
            for dy in range(-self.glow_radius, self.glow_radius + 1):
                if dx**2 + dy**2 <= self.glow_radius**2:
                    glow_surface.blit(glow_base_surface, (center_x + dx, center_y + dy))
                    
        # Draw the bright main text in the center
        glow_surface.blit(base_surface, (center_x, center_y))
        
        return glow_surface
        
    def get_surface(self):
        return self._surface

    def update_text(self, new_text):
        if self.text != new_text:
            self.text = new_text
            self._surface = self._pre_render()
            
    def draw(self, surface, position):
        """Draws the pre-rendered glowing text onto the target surface."""
        surface.blit(self._surface, position)
