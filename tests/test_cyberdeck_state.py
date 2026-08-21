#!/usr/bin/env python3
"""
test_cyberdeck_state.py — unit tests for CyberdeckState hacker terminal.
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

from states.cyberdeck_state import CyberdeckState, NODES


class MockStateManager:
    def __init__(self):
        self.current_state_name = "cyberdeck"
        self.states = {}

    def change_state(self, name):
        self.current_state_name = name


def test_cyberdeck_lifecycle():
    manager = MockStateManager()
    state = CyberdeckState(manager)
    manager.states["cyberdeck"] = state

    # Verify sprite frames loaded
    assert len(state.slicer_frames) == 8, f"Expected 8 slicer frames, got {len(state.slicer_frames)}"
    assert len(state.ice_frames) == 8, f"Expected 8 ICE frames, got {len(state.ice_frames)}"

    # Enter
    state.enter()
    assert state.t == 0.0
    assert not state.breaching
    assert not state.breached

    # Update & Animation loop
    for _ in range(40):
        state.update(0.05)

    # Draw to screen & pomodoro badge
    state.draw(surface)
    state.draw_pomodoro(surface, 900, "work")
    state.draw_pomodoro(surface, 300, "break")
    print("[PASS] CyberdeckState lifecycle & render test")


def test_cyberdeck_hacking_gameplay():
    manager = MockStateManager()
    state = CyberdeckState(manager)
    state.enter()

    # Move cursor to scan next node
    initial_idx = state.node_idx
    state.move_cursor(1)
    assert state.node_idx == (initial_idx + 1) % len(NODES)

    # Activate (Breach ICE)
    state.activate()
    assert state.breaching
    assert not state.breached

    # Simulate intrusion progress to completion (12 seconds)
    for _ in range(150):
        state.update(0.1)

    assert state.breached, "Expected node to be breached after update loop"
    assert state.breach_progress >= 1.0

    # Extract Intel (Green Button)
    state.on_green_button()
    assert "PAYLOAD EXTRACTED" in state.status_msg

    # Purge Trace (Red Button)
    state.on_red_button()
    assert not state.breaching
    assert not state.breached
    assert state.trace_pct == 0.0

    # Toggle Ghost Protocol
    state.on_toggle(True)
    assert state.stealth_on
    assert state.toggle_label() == "STEALTH"

    state.on_toggle(False)
    assert not state.stealth_on
    assert state.toggle_label() == "UNCLOAKED"

    print("[PASS] CyberdeckState hacking gameplay & controls test")


def main():
    test_cyberdeck_lifecycle()
    test_cyberdeck_hacking_gameplay()
    print("All CyberdeckState unit tests passed successfully!")


if __name__ == "__main__":
    main()
