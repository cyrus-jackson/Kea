"""
cyberdeck_state.py
------------------
THE CYBERDECK — clandestine underground slicer & hacker terminal.

A Star Wars astromech slicer meets dystopian cyberpunk matrix deck:
- Dual 8-frame animated sprite viewports:
    Left:  Kea Astromech Slicer Droid deploying cyber probe & laser sparks.
    Right: Rotating 3D Holographic Security ICE (Intrusion Countermeasure Electronics) Core.
- Real-time animated laser data streams, cascading hex memory dumps, and security trace meters.
- Interactive node scanning, icebreaking, intel dumping, and stealth proxy cloaking.

Controls:
    ENCODER turn    Scan / tune target subgrid nodes (Arasaka, Orbital, Bay 94, Underground, Biolab)
    ENCODER press   BREACH ICE — execute intrusion hack routine with laser sparks & audio chirp
    GREEN           EXTRACT INTEL — dump decrypted data payload into machine Lifebook
    RED             PURGE TRACE — emergency disconnect & memory buffer wipe
    TOGGLE          GHOST PROTOCOL (Stealth Proxy cloaking On/Off)
"""

import math
import os
import random
import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT
from states.base_state import State
from ui import palette as pal
from backend import lifebook, voice, vitals

SCALE = SCREEN_HEIGHT / 480.0


def s(v):
    return max(1, int(v * SCALE))


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SLICER_DIR = os.path.join(ROOT, "assets", "sprites", "slicer")
ICE_DIR = os.path.join(ROOT, "assets", "sprites", "ice_core")

NODES = [
    {
        "id": "ARASAKA_SUBGRID_07",
        "name": "ARASAKA MAIN SUBGRID",
        "corp": "ARASAKA NETSYS",
        "ice": "BLACK ICE v3.2",
        "diff": 4,
        "payload": "PROJECT CHROMEWING // ORBITAL SHIPMENT SCHEMATICS DECRYPTED",
        "accent": pal.MAGENTA,
    },
    {
        "id": "ORBITAL_DEFENSE_SAT",
        "name": "ORBITAL ARRAY RELAY",
        "corp": "DEFENSE COMM GRID",
        "ice": "MILITARY CIPHER 256",
        "diff": 5,
        "payload": "SATELLITE TELEMETRY // TRACKING 12 CLANDESTINE FREIGHTERS",
        "accent": pal.CYAN,
    },
    {
        "id": "BAY94_FREIGHT_MANIFEST",
        "name": "BAY 94 STARPORT LOGS",
        "corp": "OUTER RIM SMUGGLERS",
        "ice": "CUSTOM REROUTER",
        "diff": 2,
        "payload": "CONTRABAND MANIFEST // 40 TONS HYPERDRIVE CORES IN DOCK 03",
        "accent": pal.AMBER,
    },
    {
        "id": "UNDERGROUND_SHADOW_BBS",
        "name": "NEON SPRAWL SHADOW BBS",
        "corp": "ROGUE NETRUNNERS",
        "ice": "PROXY HOPPER",
        "diff": 1,
        "payload": "PIRATE AUDIO BROADCAST // ASTROMECH FIRMWARE PATCH v9.4",
        "accent": pal.ACID,
    },
    {
        "id": "BIOLAB_ARCHIVE_NODE",
        "name": "BIO-VAT GENETIC ARCHIVE",
        "corp": "GEN-TECH SYNTHETICS",
        "ice": "BIO-NEURAL FIREWALL",
        "diff": 3,
        "payload": "SPECIMEN 42 CULTIVATION SEQUENCE // MUTATION RATE STABLE",
        "accent": pal.ICE,
    },
]


class CyberdeckState(State):
    """Clandestine hacker terminal with dual 8-frame sprite animation engines."""

    def __init__(self, state_manager):
        super().__init__(state_manager)
        pygame.font.init()

        self.font_title = pygame.font.Font(None, s(22))
        self.font_node = pygame.font.Font(None, s(28))
        self.font_hex = pygame.font.Font(None, s(15))
        self.font_body = pygame.font.Font(None, s(17))
        self.font_small = pygame.font.Font(None, s(14))

        # Load 8-frame sprite sets
        self.slicer_frames = self._load_frames(SLICER_DIR, 8)
        self.ice_frames = self._load_frames(ICE_DIR, 8)

        # State / Gameplay variables
        self.node_idx = 0
        self.stealth_on = True
        self.breaching = False
        self.breached = False
        self.breach_progress = 0.0
        self.trace_pct = 0.0

        # Animation timers
        self.slicer_frame_idx = 0
        self.slicer_timer = 0.0
        self.ice_frame_idx = 0
        self.ice_timer = 0.0
        self.data_pulse = 0.0
        self.t = 0.0

        # Matrix / Hex stream buffer
        self.hex_lines = [self._gen_hex() for _ in range(7)]
        self.hex_timer = 0.0

        # Feedback
        self.status_msg = ""
        self.status_timer = 0.0
        self.glitch_flash = 0.0

        self._bg = self._build_bg()

    def _load_frames(self, directory, count):
        frames = []
        for i in range(count):
            p = os.path.join(directory, f"frame_{i}.png")
            if os.path.exists(p):
                try:
                    surf = pygame.image.load(p).convert_alpha()
                    frames.append(surf)
                except Exception:
                    pass
        return frames

    def _gen_hex(self):
        bytes_str = " ".join(f"{random.randint(0, 255):02X}" for _ in range(6))
        addr = f"0x{random.randint(0x1000, 0xFFFF):04X}"
        return f"{addr} : {bytes_str}"

    def _build_bg(self):
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(pal.VOID)

        # Grid
        g = pal.grid((SCREEN_WIDTH, SCREEN_HEIGHT), colour=pal.GRID, step=s(20))
        surf.blit(g, (0, 0))

        # Top diagnostic rail
        pygame.draw.line(surf, pal.EDGE, (s(10), s(32)), (SCREEN_WIDTH - s(10), s(32)), 1)

        # Dual Viewport bezels (Left Slicer Droid, Right ICE Core)
        box_w = (SCREEN_WIDTH - s(48)) // 2
        box_h = s(190)

        # Left Bezel (Slicer)
        slicer_rect = pygame.Rect(s(14), s(42), box_w, box_h)
        pal.bevel(surf, slicer_rect, colour=pal.EDGE, cut=s(6))

        # Right Bezel (ICE Core)
        ice_rect = pygame.Rect(s(14) + box_w + s(10), s(42), box_w, box_h)
        pal.bevel(surf, ice_rect, colour=pal.EDGE, cut=s(6))

        # Bottom Terminal Box
        term_rect = pygame.Rect(s(14), s(240), SCREEN_WIDTH - s(28), s(142))
        pal.bevel(surf, term_rect, colour=pal.EDGE, cut=s(6))

        return surf

    # ── Lifecycle ──────────────────────────────────────────────────────────
    def enter(self):
        self.t = 0.0
        self.breaching = False
        self.breached = False
        self.breach_progress = 0.0
        self.trace_pct = max(0.0, self.trace_pct - 15.0)
        self.status_msg = "CYBERDECK INTERCEPT ONLINE"
        self.status_timer = 2.5
        voice.say("wake")

    # ── Controls ───────────────────────────────────────────────────────────
    def move_cursor(self, delta):
        """Encoder Turn: Tune target node frequency."""
        self.node_idx = (self.node_idx + delta) % len(NODES)
        self.breaching = False
        self.breached = False
        self.breach_progress = 0.0
        node = NODES[self.node_idx]
        self.status_msg = f"SCANNING: {node['name']}"
        self.status_timer = 2.0
        voice.say("blip")
        return True

    def activate(self):
        """Encoder Press: BREACH ICE / SLICE."""
        if self.breached:
            self.status_msg = "NODE ALREADY COMPROMISED"
            self.status_timer = 1.5
            voice.say("blip")
            return True

        self.breaching = True
        self.status_msg = "DEPLOYING ICEBREAKER PROBE..."
        self.status_timer = 2.0
        voice.say("curious")
        return True

    def on_green_button(self):
        """GREEN Button: Extract Intel & Dump Payload."""
        if not self.breached:
            self.status_msg = "ACCESS DENIED: BREACH REQUIRED"
            self.status_timer = 2.0
            voice.say("alarm")
            return True

        node = NODES[self.node_idx]
        hacks = lifebook.bump("intel_hacks")
        lifebook.bump("intel_bytes", 512 * node["diff"])
        voice.say("happy")
        self.status_msg = f"PAYLOAD EXTRACTED! [HACKS: {hacks}]"
        self.status_timer = 3.0
        self.glitch_flash = 0.3
        return True

    def on_red_button(self):
        """RED Button: Purge Trace & Emergency Wipe."""
        self.breaching = False
        self.breached = False
        self.breach_progress = 0.0
        self.trace_pct = 0.0
        self.glitch_flash = 0.5
        self.status_msg = "TRACE PURGED // DISCONNECTED"
        self.status_timer = 2.5
        voice.say("worried")
        return True

    def on_toggle(self, on):
        """Toggle Switch: Ghost Protocol (Stealth Proxy)."""
        self.stealth_on = on
        self.status_msg = f"GHOST PROTOCOL: {'ENGAGED' if on else 'DISENGAGED'}"
        self.status_timer = 2.0
        voice.say("question" if on else "blip")

    def toggle_label(self):
        return "STEALTH" if self.stealth_on else "UNCLOAKED"

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.activate()
                elif event.key == pygame.K_g:
                    self.on_green_button()
                elif event.key == pygame.K_r:
                    self.on_red_button()
                elif event.key == pygame.K_LEFT:
                    self.move_cursor(-1)
                elif event.key == pygame.K_RIGHT:
                    self.move_cursor(1)

    # ── Update ─────────────────────────────────────────────────────────────
    def update(self, dt):
        self.t += dt
        if self.status_timer > 0:
            self.status_timer -= dt
        if self.glitch_flash > 0:
            self.glitch_flash -= dt

        # Animate Slicer Droid
        # If breaching, slicer probes rapidly (frames 3-6: sparks & data)
        slicer_speed = 0.07 if self.breaching else 0.13
        self.slicer_timer += dt
        if self.slicer_timer >= slicer_speed:
            self.slicer_timer = 0.0
            if self.slicer_frames:
                if self.breaching:
                    # Loop hacking sparks frames (3 through 6)
                    self.slicer_frame_idx = 3 + ((self.slicer_frame_idx - 3 + 1) % 4)
                else:
                    self.slicer_frame_idx = (self.slicer_frame_idx + 1) % len(self.slicer_frames)

        # Animate ICE Core (rotates smoothly)
        ice_speed = 0.06 if self.breaching else 0.12
        self.ice_timer += dt
        if self.ice_timer >= ice_speed:
            self.ice_timer = 0.0
            if self.ice_frames:
                self.ice_frame_idx = (self.ice_frame_idx + 1) % len(self.ice_frames)

        # Hex stream generator
        self.hex_timer += dt
        if self.hex_timer >= (0.05 if self.breaching else 0.25):
            self.hex_timer = 0.0
            self.hex_lines.pop(0)
            self.hex_lines.append(self._gen_hex())

        # Breaching Logic
        if self.breaching and not self.breached:
            node = NODES[self.node_idx]
            speed = (1.0 / node["diff"]) * 0.45
            self.breach_progress += speed * dt

            # Trace accumulation
            trace_rate = (1.5 if self.stealth_on else 6.0)
            self.trace_pct = min(100.0, self.trace_pct + trace_rate * dt)

            if self.breach_progress >= 1.0:
                self.breach_progress = 1.0
                self.breaching = False
                self.breached = True
                self.slicer_frame_idx = 7
                voice.say("happy")
                self.status_msg = "ICE CRACKED // ACCESS GRANTED"
                self.status_timer = 3.0

    # ── Draw ────────────────────────────────────────────────────────────────
    def draw(self, surface):
        surface.blit(self._bg, (0, 0))

        node = NODES[self.node_idx]
        accent = node["accent"]
        box_w = (SCREEN_WIDTH - s(48)) // 2
        box_h = s(190)

        # ── Header Rail ──────────────────────────────────────────────────
        title = self.font_title.render("CYBERDECK // SLICER MATRIX", True, pal.INK)
        surface.blit(title, (s(14), s(8)))

        # Trace Meter & Cloak
        t_col = pal.BLOOD if self.trace_pct > 75 else pal.AMBER if self.trace_pct > 40 else pal.ACID
        trace_str = f"TRACE: {int(self.trace_pct):02d}%"
        t_txt = self.font_title.render(trace_str, True, t_col)
        surface.blit(t_txt, (SCREEN_WIDTH - t_txt.get_width() - s(14), s(8)))

        # ── Left Viewport: Slicer Droid ──────────────────────────────────
        slicer_x = s(14)
        slicer_y = s(42)
        tag_l = self.font_small.render("ROGUE SLICER [KEA-01]", True, pal.CYAN)
        surface.blit(tag_l, (slicer_x + s(10), slicer_y + s(8)))

        if self.slicer_frames and 0 <= self.slicer_frame_idx < len(self.slicer_frames):
            frame = self.slicer_frames[self.slicer_frame_idx]
            spr_w, spr_h = s(140), s(155)
            scaled = pygame.transform.smoothscale(frame, (spr_w, spr_h))
            surface.blit(scaled, (slicer_x + (box_w - spr_w) // 2, slicer_y + s(25)))

        # ── Right Viewport: Security ICE Core ────────────────────────────
        ice_x = s(14) + box_w + s(10)
        ice_y = s(42)
        tag_r = self.font_small.render(f"NODE: {node['ice']}", True, accent)
        surface.blit(tag_r, (ice_x + s(10), ice_y + s(8)))

        # ICE Halo
        h = pal.halo(s(55), accent if not self.breached else pal.ACID, alpha=60)
        surface.blit(h, (ice_x + box_w // 2 - h.get_width() // 2,
                         ice_y + box_h // 2 - h.get_height() // 2 + s(10)))

        if self.ice_frames and 0 <= self.ice_frame_idx < len(self.ice_frames):
            frame = self.ice_frames[self.ice_frame_idx]
            spr_w, spr_h = s(140), s(155)
            scaled = pygame.transform.smoothscale(frame, (spr_w, spr_h))
            surface.blit(scaled, (ice_x + (box_w - spr_w) // 2, ice_y + s(25)))

        # ── Laser Data Beam (bridging left to right when breaching/breached) ──
        if self.breaching or self.breached:
            beam_y = slicer_y + box_h // 2 + s(15)
            x_start = slicer_x + box_w - s(15)
            x_end = ice_x + s(15)
            beam_col = pal.ACID if self.breached else pal.CYAN

            # Glowing data line
            pygame.draw.line(surface, beam_col, (x_start, beam_y), (x_end, beam_y), 3)
            pygame.draw.line(surface, pal.WHITE, (x_start, beam_y), (x_end, beam_y), 1)

            # Flowing data packets
            pulse_off = int((self.t * 120) % (x_end - x_start))
            pygame.draw.circle(surface, pal.GOLD, (x_start + pulse_off, beam_y), s(4))

        # ── Bottom Terminal Area ─────────────────────────────────────────
        term_y = s(246)
        term_x = s(24)

        # Target Node Title
        pal.blit_glow(surface, self.font_node, node["name"], accent,
                      (term_x, term_y), radius=s(2), strength=90)

        # Security & Defense Stats
        corp_str = f"CORP: {node['corp']}  ·  SECURITY LEVEL {node['diff']}/5"
        c_txt = self.font_small.render(corp_str, True, pal.INK_DIM)
        surface.blit(c_txt, (term_x, term_y + s(26)))

        # Breaching Progress Bar
        bar_w = SCREEN_WIDTH - s(48)
        bar_y = term_y + s(44)
        pygame.draw.rect(surface, pal.PANEL, (term_x, bar_y, bar_w, s(8)), border_radius=s(2))
        fill_w = int(bar_w * self.breach_progress)
        if fill_w > 0:
            fill_col = pal.ACID if self.breached else pal.CYAN
            pygame.draw.rect(surface, fill_col, (term_x, bar_y, fill_w, s(8)), border_radius=s(2))
        pygame.draw.rect(surface, pal.EDGE, (term_x, bar_y, bar_w, s(8)), 1, border_radius=s(2))

        # Decrypted Payload or Hex Stream
        if self.breached:
            # Show decrypted payload
            p_txt = self.font_body.render(f">> INTEL: {node['payload']}", True, pal.GOLD)
            surface.blit(p_txt, (term_x, bar_y + s(14)))
            h_hint = self.font_small.render("PRESS [GREEN] TO EXTRACT INTEL TO LIFEBOOK", True, pal.ACID)
            surface.blit(h_hint, (term_x, bar_y + s(34)))
        else:
            # Show rolling hex matrix stream
            hex_sample = " // ".join(self.hex_lines[-2:])
            hx_txt = self.font_hex.render(f">> STREAM: {hex_sample}", True, pal.INK_FAINT)
            surface.blit(hx_txt, (term_x, bar_y + s(14)))
            act_txt = self.font_small.render("DIAL: SCAN NODE  ·  PRESS: EXECUTE ICEBREAKER", True, pal.INK_DIM)
            surface.blit(act_txt, (term_x, bar_y + s(34)))

        # Status Overlay (or CRT Scanline Glitch)
        if self.status_timer > 0:
            st_txt = self.font_small.render(f"// {self.status_msg}", True, pal.AMBER)
            surface.blit(st_txt, (term_x, term_y + s(115)))

        if self.glitch_flash > 0:
            scan = pal.scanlines((SCREEN_WIDTH, SCREEN_HEIGHT), alpha=70, step=s(2))
            surface.blit(scan, (0, 0))

    def draw_pomodoro(self, surface, time_left, mode):
        """Draw unique Cyberdeck style Pomodoro badge."""
        mins, secs = int(time_left) // 60, int(time_left) % 60
        c = pal.MAGENTA if mode == "work" else pal.ACID
        txt = self.font_small.render(f"DECK-LOCK {mins:02d}:{secs:02d}", True, c)
        rect = txt.get_rect(topright=(SCREEN_WIDTH - s(14), s(38)))
        box = rect.inflate(s(8), s(4))
        pygame.draw.rect(surface, pal.VOID, box, border_radius=s(3))
        pygame.draw.rect(surface, c, box, 1, border_radius=s(3))
        surface.blit(txt, rect)
