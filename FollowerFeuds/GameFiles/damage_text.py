import pygame
from constants import Colours


class DamageText:
    """
    Represents a floating damage (or healing) number that appears briefly
    on screen and fades out over time.
    """

    def __init__(self, x, y, value, colour=Colours.WHITE, prefix="-"):
        """
        Create a new floating text instance.

        :param x: Initial x position (screen coordinates)
        :param y: Initial y position (screen coordinates)
        :param value: Numeric value to display
        :param colour: Text colour (defaults to white)
        :param prefix: String placed before the value (e.g. '-' for damage, '+' for healing)
        """
        self.x = x
        self.y = y
        self.value = value
        self.colour = colour
        self.prefix = prefix

        # Time the text was created (used for fading and lifetime)
        self.start_time = pygame.time.get_ticks()

        # How long the text should stay on screen (milliseconds)
        self.lifetime = 1000

        # Vertical movement speed (negative moves upwards)
        self.speed = -0.7

    def update(self):
        """
        Update the position of the damage text.
        Called once per frame.
        """
        self.y += self.speed

    def is_alive(self):
        """
        Check whether the text should still be displayed.

        :return: True if within its lifetime, False otherwise
        """
        return pygame.time.get_ticks() - self.start_time < self.lifetime

    def draw(self, win, font):
        """
        Render the damage text to the screen with a fade-out effect.

        :param win: The pygame surface (window) to draw onto
        :param font: Pre-created pygame font (avoids recreating fonts every frame)
        """
        # Calculate how long the text has been alive
        elapsed = pygame.time.get_ticks() - self.start_time

        # Fade out alpha from 255 → 0 over the lifetime
        alpha = max(0, 255 - int((elapsed / self.lifetime) * 255))

        # Render the text
        text_surface = font.render(f"{self.prefix}{self.value}", True, self.colour)

        # Apply transparency
        text_surface.set_alpha(alpha)

        # Centre the text at its current position
        rect = text_surface.get_rect(center=(int(self.x), int(self.y)))

        # Draw to the window
        win.blit(text_surface, rect)