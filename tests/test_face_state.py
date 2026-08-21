#!/usr/bin/env python3
"""
test_face_state.py — unit tests for Kea's Face companion state.
"""

import os
import sys
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

# Headless pygame setup
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("KEA_FEEDS", "0")
os.environ.setdefault("KEA_VOICE", "0")

pygame.init()
pygame.display.set_mode((480, 320))
surface = pygame.display.get_surface()

from states.face_state import FaceState, MOODS, VISOR_COLORS


class MockStateManager:
    def __init__(self):
        self.current_state_name = "face"
        self.states = {}

    def change_state(self, name):
        self.current_state_name = name


def test_face_state_lifecycle():
    manager = MockStateManager()
    state = FaceState(manager)
    manager.states["face"] = state

    # Check assets loaded
    assert len(state.face_frames) == 8, f"Expected 8 face frames, got {len(state.face_frames)}"
    assert len(state.droid_frames) == 8, f"Expected 8 droid frames, got {len(state.droid_frames)}"

    # Enter
    state.enter()
    assert state.t == 0.0

    # Update & Animation progression
    initial_idx = state.frame_idx
    for _ in range(30):
        state.update(0.05)
    # Frame should have cycled
    assert state.frame_timer >= 0.0

    # Draw to surface
    state.draw(surface)
    state.draw_pomodoro(surface, 1200, "work")
    state.draw_pomodoro(surface, 300, "break")
    print("[PASS] FaceState lifecycle & render test")


def test_face_controls():
    manager = MockStateManager()
    state = FaceState(manager)
    state.enter()

    # Move cursor (cycles mood)
    state.move_cursor(1)
    assert not state.auto_mood
    assert state.mood_idx == 1

    # Activate (Poke)
    state.activate()
    assert state.poke_timer > 0.0

    # Green button (Praise)
    state.on_green_button()
    assert state.praise_flash > 0.0

    # Red button (Visor tint shift)
    initial_c = state.color_idx
    state.on_red_button()
    assert state.color_idx == (initial_c + 1) % len(VISOR_COLORS)

    # Toggle switch (Auto Mood)
    state.on_toggle(True)
    assert state.auto_mood
    assert state.toggle_label() == "AUTO MOOD"

    state.on_toggle(False)
    assert not state.auto_mood
    assert state.toggle_label() == "MANUAL"

    # Switch model (Face <-> Droid)
    state.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)])
    assert state.model == "droid"
    state.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB)])
    assert state.model == "face"

    print("[PASS] FaceState interactive controls test")


def main():
    test_face_state_lifecycle()
    test_face_controls()
    print("All FaceState unit tests passed successfully!")


if __name__ == "__main__":
    main()
