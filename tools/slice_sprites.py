#!/usr/bin/env python3
"""
slice_sprites.py — slice generated sprite sheets into individual PNG frames.

Extracts:
1. CRT Face 8-frame animation (4x2 grid) -> assets/sprites/face/
2. Droid 8-frame animation (1x8 strip) -> assets/sprites/droid/
3. Slicer Droid 8-frame animation (4x2 grid) -> assets/sprites/slicer/
4. ICE Core 8-frame animation (4x2 grid) -> assets/sprites/ice_core/
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    pygame.init()
except ImportError:
    print("Error: Pygame is required for slicing.")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACE_SHEET = "/Users/cyrusjackson/.gemini/antigravity/brain/997451fc-2f81-4815-8846-f3badec6ba75/kea_face_blink_8frames_1787333367991.jpg"
DROID_SHEET = "/Users/cyrusjackson/.gemini/antigravity/brain/997451fc-2f81-4815-8846-f3badec6ba75/kea_idle_anim_8frames_1787333353163.jpg"
SLICER_SHEET = "/Users/cyrusjackson/.gemini/antigravity/brain/997451fc-2f81-4815-8846-f3badec6ba75/slicer_droid_8frames_1787333965751.jpg"
ICE_SHEET = "/Users/cyrusjackson/.gemini/antigravity/brain/997451fc-2f81-4815-8846-f3badec6ba75/ice_core_8frames_1787333994949.jpg"

FACE_DIR = os.path.join(ROOT, "assets", "sprites", "face")
DROID_DIR = os.path.join(ROOT, "assets", "sprites", "droid")
SLICER_DIR = os.path.join(ROOT, "assets", "sprites", "slicer")
ICE_DIR = os.path.join(ROOT, "assets", "sprites", "ice_core")


def transparent_key(surface, threshold=20):
    """Return RGBA surface with black pixels keyed out."""
    w, h = surface.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    out.blit(surface, (0, 0))
    
    px = pygame.PixelArray(out)
    for y in range(h):
        for x in range(w):
            color = out.unmap_rgb(px[x, y])
            r, g, b = color.r, color.g, color.b
            if r <= threshold and g <= threshold and b <= threshold:
                px[x, y] = (0, 0, 0, 0)
    del px
    return out


def slice_grid_4x2(sheet_path, out_dir, threshold=20):
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.exists(sheet_path):
        print(f"Error: {sheet_path} not found")
        return False
    
    sheet = pygame.image.load(sheet_path)
    w, h = sheet.get_size()
    cols, rows = 4, 2
    fw = w // cols
    fh = h // rows
    
    for i in range(8):
        row = i // cols
        col = i % cols
        rect = pygame.Rect(col * fw, row * fh, fw, fh)
        frame = pygame.Surface((fw, fh), pygame.SRCALPHA)
        frame.blit(sheet, (0, 0), rect)
        
        proc = transparent_key(frame, threshold=threshold)
        out_path = os.path.join(out_dir, f"frame_{i}.png")
        pygame.image.save(proc, out_path)
        print(f"Saved {out_path} ({fw}x{fh})")
    return True


def slice_strip_8x1(sheet_path, out_dir, threshold=18):
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.exists(sheet_path):
        print(f"Error: {sheet_path} not found")
        return False
    
    sheet = pygame.image.load(sheet_path)
    w, h = sheet.get_size()
    cols = 8
    fw = w // cols
    fh = h
    
    for i in range(cols):
        rect = pygame.Rect(i * fw, 0, fw, fh)
        frame = pygame.Surface((fw, fh), pygame.SRCALPHA)
        frame.blit(sheet, (0, 0), rect)
        
        proc = transparent_key(frame, threshold=threshold)
        out_path = os.path.join(out_dir, f"frame_{i}.png")
        pygame.image.save(proc, out_path)
        print(f"Saved {out_path} ({fw}x{fh})")
    return True


def main():
    print("Slicing CRT Face 8-frame animation...")
    slice_grid_4x2(FACE_SHEET, FACE_DIR, threshold=22)
    
    print("\nSlicing Droid 8-frame animation...")
    slice_strip_8x1(DROID_SHEET, DROID_DIR, threshold=18)
    
    print("\nSlicing Slicer Droid 8-frame animation...")
    slice_grid_4x2(SLICER_SHEET, SLICER_DIR, threshold=22)
    
    print("\nSlicing ICE Core 8-frame animation...")
    slice_grid_4x2(ICE_SHEET, ICE_DIR, threshold=22)
    
    print("\nAll sprite sets successfully sliced!")


if __name__ == "__main__":
    main()
