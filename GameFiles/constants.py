import pygame


class Colours:
    """Common RGB colour constants used throughout the game (British spelling: 'Colours')."""

    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    GREY = (125, 125, 125)

    RED = (255, 0, 0)
    DARK_RED = (180, 0, 0)

    BLUE = (100, 100, 255)
    GREEN = (0, 255, 0)
    CYAN = (0, 255, 255)

    ORANGE = (255, 165, 0)
    PURPLE = (128, 0, 128)
    YELLOW = (255, 255, 0)


class Fonts:
    """
    Centralised font storage.

    Create the fonts once and reuse them everywhere to:
    - avoid repeatedly constructing fonts (slower and harder to manage)
    - keep sizing/style consistent across the UI

    Note:
        pygame.font must be initialised before creating fonts.
        Usually this is handled by calling `pygame.init()` (or `pygame.font.init()`)
        near the start of your program.
    """

    def __init__(self) -> None:
        # Large on-screen text (countdown / "GO!" / match clock display).
        self.FONT = pygame.font.SysFont("Helvetica", 80)

        # Winner announcement / end-of-round messages.
        self.WINNER_FONT = pygame.font.SysFont("Helvetica", 40)

        # Small HUD text (health values, labels).
        self.HEALTH_FONT = pygame.font.SysFont("Helvetica", 18)

        # Combat feedback text (damage numbers, hit indicators).
        self.DAMAGE_FONT = pygame.font.SysFont("Helvetica", 24)

        # Main menu / title screen heading.
        self.GAME_TITLE_FONT = pygame.font.SysFont("Helvetica", 60)