import math
import random
from typing import List, Optional

import pygame

from config import SpecialRole
from constants import Colours
from damage_text import DamageText


class Spinner:
    """
    A single spinner (player/AI) in the arena.

    Responsibilities:
    - Maintain physics state (position, velocity) and basic arena bouncing
    - Track health and damage dealt
    - Manage power-ups (shield, dagger, heal) and status effects (poison)
    - Handle role-specific behaviour (Titan/Venom/Glitch/Clone)
    - Render itself and its visual effects
    """

    def __init__(
        self,
        x: float,
        y: float,
        image: pygame.Surface,
        speed: int,
        mass: int,
        name: str,
        team: str = "TeamA",
        radius: int = 75,
        role: SpecialRole = SpecialRole.NONE,
    ):
        # --- Core spatial state ---
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0

        # --- Identity / stats ---
        self.speed = speed
        self.mass = mass
        self.name = name
        self.team = team
        self.role = role

        # --- Visuals / collision shape ---
        self.original_image = image
        self.radius = radius
        self.image = image
        self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))

        # --- Combat / UI ---
        self.health = 100
        self.damage_dealt = 0
        self.damage_texts: List[DamageText] = []

        # --- Power-ups (timed) ---
        self.shield = False
        self.shield_end_time = 0  # pygame ticks (ms)

        self.carrying_dagger = False
        self.dagger_end_time = 0  # pygame ticks (ms)

        self.heal = False
        self.heal_end_time = 0  # pygame ticks (ms)

        # --- Venom: poison over time ---
        self.poison_ticks = 0              # how many ticks remain
        self.poison_end_time = 0           # when the next tick should happen (ms)
        self.last_poison_source: Optional["Spinner"] = None  # credit damage to attacker

        # --- Glitch: phasing behaviour ---
        self.phasing_through: Optional["Spinner"] = None
        self.phasing_start_time = 0
        self.glitch_charges = 3 if role == SpecialRole.GLITCH else 0

        # --- Clone: one-time clone spawning behaviour ---
        self.clone_created = False
        self.clone_spawn_time = 0

        # Apply any role-based stat changes and ensure image/rect match radius.
        self._apply_role_modifiers()

    # ============================================================
    # Role modifiers
    # ============================================================
    def _apply_role_modifiers(self) -> None:
        """
        Adjust stats and visuals based on role.

        Important: this also rescales the sprite to match `self.radius`
        and rebuilds the rect.
        """
        if self.role == SpecialRole.TITAN:
            # Titan: bigger, tougher, but slower (with a speed cap)
            self.health = min(int(self.health * 1.3), 130)
            self.radius = int(self.radius * 1.5)
            self.speed = max(1, int(self.speed * 0.66))
            if self.speed > 4:
                self.speed = 4

        # Scale the image to match the (possibly modified) radius.
        self.image = pygame.transform.smoothscale(
            self.original_image,
            (self.radius * 2, self.radius * 2),
        )
        self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))

    # ============================================================
    # Movement
    # ============================================================
    def start_moving(self) -> None:
        """Give the spinner an initial random direction at its configured speed."""
        angle = random.uniform(0, 2 * math.pi)
        self.vx = self.speed * math.cos(angle)
        self.vy = self.speed * math.sin(angle)

    def move(self, bounds: pygame.Rect) -> None:
        """
        Move the spinner and bounce off the arena bounds.

        Notes:
        - `bounds` is the playable area rectangle.
        - We clamp the centre position so the whole spinner remains visible.
        """
        # Update position from velocity.
        self.x += self.vx
        self.y += self.vy
        self.rect.center = (int(self.x), int(self.y))

        # Arena edges adjusted so the spinner (circle) stays inside.
        left = bounds.left + self.radius
        right = bounds.right - self.radius
        top = bounds.top + self.radius
        bottom = bounds.bottom - self.radius

        # Bounce by reflecting velocity when we hit an edge.
        if self.x <= left or self.x >= right:
            self.vx *= -1
        if self.y <= top or self.y >= bottom:
            self.vy *= -1

        # Clamp after bounce to prevent sticking outside due to overshoot.
        self.x = max(left, min(right, self.x))
        self.y = max(top, min(bottom, self.y))

        # Timed effects tick down from here.
        self._update_powerups()
        self._update_status_effects()

    # ============================================================
    # Power-ups and status effects
    # ============================================================
    def _update_powerups(self) -> None:
        """Expire timed power-ups when their end time has passed."""
        now = pygame.time.get_ticks()

        if self.shield and now > self.shield_end_time:
            self.shield = False

        if self.carrying_dagger and now > self.dagger_end_time:
            self.carrying_dagger = False

        if self.heal and now > self.heal_end_time:
            self.heal = False

    def _update_status_effects(self) -> None:
        """
        Handle damage-over-time effects.

        Poison:
        - Ticks a fixed number of times
        - Each tick deals 1–2 damage (capped by remaining health)
        - Damage is credited to the original poison source (if known)
        """
        now = pygame.time.get_ticks()

        # Poison tick occurs when time has reached the next scheduled tick.
        if self.poison_ticks > 0 and now >= self.poison_end_time:
            damage = random.randint(1, 2)
            actual = min(damage, self.health)
            self.health = max(0, self.health - actual)

            # Only show numbers / credit damage if something was actually taken.
            if actual > 0:
                self.damage_texts.append(
                    DamageText(
                        self.x + random.randint(-15, 15),
                        self.y - self.radius,
                        actual,
                        colour=Colours.BLUE if self.team == "TeamA" else Colours.RED,
                    )
                )

                if self.last_poison_source:
                    self.last_poison_source.damage_dealt += actual

            # Decrement ONLY when a real tick happens.
            self.poison_ticks -= 1

            # Schedule the next tick or clear the timer if finished.
            if self.poison_ticks > 0:
                self.poison_end_time = now + 500  # next tick in 0.5 seconds
            else:
                self.poison_end_time = 0

    # ============================================================
    # Floating combat text helpers
    # ============================================================
    def add_damage_text(self, amount: int) -> None:
        """Spawn a floating damage number above this spinner."""
        if amount <= 0:
            return

        colour = Colours.BLUE if self.team == "TeamA" else Colours.RED
        self.damage_texts.append(
            DamageText(
                self.x + random.randint(-15, 15),
                self.y - self.radius,
                amount,
                colour=colour,
            )
        )

    def add_heal_text(self, amount: int) -> None:
        """Spawn a floating heal number above this spinner."""
        if amount <= 0:
            return

        self.damage_texts.append(
            DamageText(
                self.x + random.randint(-15, 15),
                self.y - self.radius,
                amount,
                colour=Colours.GREEN,
                prefix="+",
            )
        )

    # ============================================================
    # Venom
    # ============================================================
    def apply_poison(self, attacker: Optional["Spinner"] = None) -> None:
        """
        Apply poison to this spinner.

        Poison is scheduled as timed ticks rather than continuous damage.
        `attacker` is stored so they get credit for poison damage dealt.
        """
        self.poison_ticks = 4
        self.poison_end_time = pygame.time.get_ticks() + 500
        self.last_poison_source = attacker

    # ============================================================
    # Clone
    # ============================================================
    def create_clone(self, game_instance) -> None:
        """
        Spawn a clone once, when conditions are met.

        Conditions:
        - Must be the CLONE role
        - Only once per spinner
        - Only triggers when health drops to 50 or below

        Behaviour:
        - Adds a new spinner to the game with modest stats
        - Resets this spinner’s health down to 30 as a 'second wind'
        """
        if self.role != SpecialRole.CLONE:
            return
        if self.clone_created:
            return
        if self.health > 50:
            return

        clone = Spinner(
            self.x + random.randint(-50, 50),
            self.y + random.randint(-50, 50),
            self.original_image,
            speed=8,
            mass=self.mass,
            name=f"{self.name} Clone",
            team=self.team,
            radius=self.radius,
            role=SpecialRole.NONE,
        )

        clone.health = 30
        clone.clone_created = True  # prevents the clone itself making another clone
        clone.start_moving()

        # Register clone with the main game state.
        game_instance.all_spinners.append(clone)
        game_instance.initial_speed_total += 8

        # Reset this spinner’s health and mark clone creation.
        self.health = 30
        self.clone_created = True
        self.clone_spawn_time = pygame.time.get_ticks()

        game_instance.asset_manager.play_sound("clone")

    # ============================================================
    # Glitch phasing
    # ============================================================
    def check_phasing_completion(self, all_spinners: List["Spinner"], asset_manager) -> None:
        """
        Finalise a glitch phase once we have fully passed through the target spinner.

        Current rule:
        - If the glitch spinner is shielded, the phase is cancelled immediately.
        - If we have separated beyond overlap distance AND the target had a dagger,
          the dagger is removed, a charge is consumed, and the phase ends.

        Note:
        `all_spinners` is currently unused, but is kept in the signature so you can
        expand this logic later (e.g., re-targeting or multi-phase interactions).
        """
        if self.role != SpecialRole.GLITCH or self.phasing_through is None:
            return

        # Shield blocks the phasing interaction.
        if self.shield:
            asset_manager.play_sound("glitch")
            self.phasing_through = None
            self.phasing_start_time = 0
            return

        dx = self.x - self.phasing_through.x
        dy = self.y - self.phasing_through.y
        dist = math.hypot(dx, dy)
        min_dist = self.radius + self.phasing_through.radius

        # Once we’re no longer overlapping, we can complete the effect.
        if dist >= min_dist and self.phasing_through.carrying_dagger:
            self.phasing_through.carrying_dagger = False
            self.glitch_charges -= 1
            self.phasing_through = None
            self.phasing_start_time = 0

    # ============================================================
    # Drawing
    # ============================================================
    def draw(self, win: pygame.Surface, fonts) -> None:
        """Render the spinner, its effects, floating text, and name tag."""
        self._draw_role_effects(win)

        if self.shield:
            self._draw_shield_glow(win)

        if self.carrying_dagger:
            self._draw_dagger_spikes(win)

        # Base sprite
        win.blit(self.image, self.rect)

        # Floating damage/heal numbers
        for dmg in self.damage_texts[:]:
            dmg.update()
            if dmg.is_alive():
                dmg.draw(win, fonts.DAMAGE_FONT)
            else:
                self.damage_texts.remove(dmg)

        # Heal overlay is drawn last so it sits on top of the sprite.
        if self.heal:
            self._draw_heal(win)

        self._draw_name(win, fonts.HEALTH_FONT)

    # ------------------------------------------------------------
    # Visual effects
    # ------------------------------------------------------------
    def _draw_role_effects(self, win: pygame.Surface) -> None:
        """Simple ring outlines to indicate special roles."""
        if self.role == SpecialRole.VENOM:
            pygame.draw.circle(win, Colours.GREEN, (int(self.x), int(self.y)), self.radius + 4, 3)
        elif self.role == SpecialRole.GLITCH and self.glitch_charges > 0:
            pygame.draw.circle(win, Colours.PURPLE, (int(self.x), int(self.y)), self.radius + 4, 2)
        elif self.role == SpecialRole.CLONE:
            pygame.draw.circle(win, Colours.BLUE, (int(self.x), int(self.y)), self.radius + 4, 3)

    def _draw_shield_glow(self, win: pygame.Surface) -> None:
        """
        Draw a pulsing cyan ring for the shield.

        Implementation detail:
        - Uses a sine wave to oscillate the brightness smoothly.
        """
        t = pygame.time.get_ticks() / 200.0
        phase = (math.sin(t) + 1) / 2  # 0..1

        # Dim cyan to bright cyan.
        r = 0
        g = int(150 + 105 * phase)
        b = int(190 + 65 * phase)
        colour = (r, g, b)

        # Slightly vary line width to give a 'glow' feel.
        width = 3 + int(4 * phase)

        pygame.draw.circle(
            win,
            colour,
            (int(self.x), int(self.y)),
            self.radius + 8,
            width,
        )

    def _draw_dagger_spikes(self, win: pygame.Surface) -> None:
        """
        Draw rotating spikes around the spinner while carrying a dagger.

        Notes:
        - Rotation direction flips for TeamB, purely for visual differentiation.
        """
        spikes = 12
        spike_length = 22
        angle_spread = 0.1
        base_offset = 10

        # Full rotation roughly every 2.5 seconds.
        rotation = (pygame.time.get_ticks() / 2500.0) * (2 * math.pi)
        if self.team == "TeamB":
            rotation = -rotation

        for i in range(spikes):
            angle = (2 * math.pi / spikes) * i + rotation

            outer = (
                self.x + math.cos(angle) * (self.radius + spike_length),
                self.y + math.sin(angle) * (self.radius + spike_length),
            )
            left = (
                self.x + math.cos(angle + angle_spread) * (self.radius + spike_length - base_offset),
                self.y + math.sin(angle + angle_spread) * (self.radius + spike_length - base_offset),
            )
            right = (
                self.x + math.cos(angle - angle_spread) * (self.radius + spike_length - base_offset),
                self.y + math.sin(angle - angle_spread) * (self.radius + spike_length - base_offset),
            )

            pygame.draw.polygon(win, Colours.DARK_RED, [left, outer, right])

    def _draw_heal(self, win: pygame.Surface) -> None:
        """
        Draw a green tint over the spinner that fades out.

        Important:
        - We copy the sprite so the alpha mask stays identical (circle stays a circle).
        - Use BLEND_RGBA_ADD so transparent pixels remain transparent.
        """
        now = pygame.time.get_ticks()

        duration = 450
        remaining = max(0, self.heal_end_time - now)
        t = remaining / duration  # 1 -> 0

        fade_alpha = int(200 * (t ** 0.6))

        tint = self.image.copy().convert_alpha()
        tint.fill((0, 255, 0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        tint.set_alpha(fade_alpha)

        win.blit(tint, self.rect)

    def _draw_name(self, win: pygame.Surface, font) -> None:
        """Render the spinner name plus a small role indicator above the sprite."""
        team_colour = Colours.BLUE if self.team == "TeamA" else Colours.RED

        role_symbol = ""
        if self.role == SpecialRole.TITAN:
            role_symbol = " [T]"
        elif self.role == SpecialRole.VENOM:
            role_symbol = " [V]"
        elif self.role == SpecialRole.GLITCH:
            role_symbol = f" [G:{self.glitch_charges}]"
        elif self.role == SpecialRole.CLONE:
            role_symbol = " [C]"

        text = font.render(self.name + role_symbol, True, team_colour)
        rect = text.get_rect(center=(int(self.x), int(self.y - self.radius - 20)))
        win.blit(text, rect)