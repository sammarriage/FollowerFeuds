import math
import random

import pygame

from config import GameConfig
from constants import Colours
from spinner import Spinner


class Item:
    """
    Base class for collectible items.

    Handles:
    - spawn/respawn timing
    - choosing a spawn location inside the play area
    - basic circular collision checks against a Spinner
    """

    def __init__(self, radius: int, spawn_delay: int, respawn_delay: int):
        # Visual/collision size of the item
        self.radius = radius

        # Timing (milliseconds)
        self.spawn_delay = spawn_delay
        self.respawn_delay = respawn_delay  # kept for future use / parity with config

        # Whether the item is currently present in the arena
        self.active = False

        # Default off-screen position until spawned
        self.x = -100
        self.y = -100

        # Timestamp used to decide when the next spawn should occur
        self.spawn_time = pygame.time.get_ticks()

    def respawn(self, bounds: pygame.Rect) -> None:
        """
        Spawn the item at a random point within `bounds`, keeping a safe margin
        from the edges so it doesn't appear half outside the arena.

        Notes:
        - We try to keep a fixed margin (100px), but clamp it for smaller arenas.
        - If the arena is too small for that margin, we fall back to just keeping
          the item fully within bounds based on its radius.
        """
        desired_margin = 100

        # Clamp the margin so we don't produce an invalid range in small arenas.
        max_margin_x = max(0, bounds.width // 2 - self.radius - 1)
        max_margin_y = max(0, bounds.height // 2 - self.radius - 1)
        margin = min(desired_margin, max_margin_x, max_margin_y)

        left = bounds.left + margin
        right = bounds.right - margin
        top = bounds.top + margin
        bottom = bounds.bottom - margin

        # If the margin makes the spawn area invalid, fall back to radius-based bounds.
        if left >= right:
            left = bounds.left + self.radius + 1
            right = bounds.right - self.radius - 1
        if top >= bottom:
            top = bounds.top + self.radius + 1
            bottom = bounds.bottom - self.radius - 1

        self.x = random.randint(int(left), int(right))
        self.y = random.randint(int(top), int(bottom))

        self.active = True
        self.spawn_time = pygame.time.get_ticks()

    def update(self, bounds: pygame.Rect) -> None:
        """
        Update spawn state.

        When inactive, this checks whether enough time has passed since the last
        spawn/despawn to bring the item back into play.
        """
        if self.active:
            return

        now = pygame.time.get_ticks()
        if now - self.spawn_time > self.spawn_delay:
            self.respawn(bounds)

    def check_collision(self, spinner: Spinner) -> bool:
        """
        Return True if `spinner` overlaps this item (circle-to-circle collision).

        If the item is inactive, collision is always False.
        """
        if not self.active:
            return False

        dx = spinner.x - self.x
        dy = spinner.y - self.y
        distance = math.hypot(dx, dy)

        return distance < (spinner.radius + self.radius)


# ==================================================
# HEALTH PACK
# ==================================================
class HealthPack(Item):
    """A simple health pickup: a green square with a white cross."""

    def __init__(self, config: GameConfig):
        super().__init__(radius=20,
                         spawn_delay=config.HEALTH_SPAWN_DELAY,
                         respawn_delay=config.HEALTH_RESPAWN_DELAY)

    def draw(self, win: pygame.Surface) -> None:
        """Draw the health pack if it's currently active."""
        if not self.active:
            return

        # Main body
        pygame.draw.rect(
            win,
            Colours.GREEN,
            (self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2),
        )

        # Cross (two rectangles)
        cross_thickness = 6
        arm_length = 10
        cx, cy = self.x, self.y

        pygame.draw.rect(
            win,
            Colours.WHITE,
            (cx - cross_thickness // 2, cy - arm_length, cross_thickness, arm_length * 2),
        )
        pygame.draw.rect(
            win,
            Colours.WHITE,
            (cx - arm_length, cy - cross_thickness // 2, arm_length * 2, cross_thickness),
        )


# ==================================================
# DAGGER
# ==================================================
class DaggerItem(Item):
    """A damage pickup, drawn as a simple red triangular 'dagger' icon."""

    def __init__(self, config: GameConfig):
        super().__init__(radius=20,
                         spawn_delay=config.DAGGER_SPAWN_DELAY,
                         respawn_delay=config.DAGGER_RESPAWN_DELAY)

    def draw(self, win: pygame.Surface) -> None:
        """Draw the dagger if it's currently active."""
        if not self.active:
            return

        points = [
            (self.x, self.y - self.radius),
            (self.x - self.radius, self.y + self.radius),
            (self.x + self.radius, self.y + self.radius),
        ]
        pygame.draw.polygon(win, Colours.DARK_RED, points)


# ==================================================
# SHIELD
# ==================================================
class ShieldItem(Item):
    """A defensive pickup, drawn as a cyan circle with a white outline."""

    def __init__(self, config: GameConfig):
        super().__init__(radius=20,
                         spawn_delay=config.SHIELD_SPAWN_DELAY,
                         respawn_delay=config.SHIELD_RESPAWN_DELAY)

    def draw(self, win: pygame.Surface) -> None:
        """Draw the shield if it's currently active."""
        if not self.active:
            return

        pygame.draw.circle(win, Colours.CYAN, (self.x, self.y), self.radius)
        pygame.draw.circle(win, Colours.WHITE, (self.x, self.y), self.radius, 2)