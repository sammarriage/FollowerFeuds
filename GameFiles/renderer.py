import pygame
from typing import Tuple, Optional, Sequence, Union

from constants import Colours, Fonts
from config import GameConfig


class Renderer:
    """
    Central place for all drawing logic.

    This class keeps rendering code out of the game loop / entity classes, so
    gameplay logic stays separate from presentation.
    """

    def __init__(self, config: GameConfig):
        self.config = config
        self.fonts = Fonts()

    # =========================
    # COUNTDOWN (3, 2, 1, GO!)
    # =========================
    def draw_countdown(self, win: pygame.Surface, count: int, centre: Tuple[int, int]) -> None:
        """
        Draws the pre-match countdown in the middle of the play area.

        Args:
            win: The main window surface to draw on.
            count: Countdown value. If > 0 draws the number, otherwise draws "GO!".
            centre: (x, y) screen position for the text centre.
        """
        text_str = str(count) if count > 0 else "GO!"
        font = self.fonts.FONT  # Use the same font as the match clock for consistency.

        text_w, text_h = font.size(text_str)
        x = centre[0] - text_w // 2
        y = centre[1] - text_h // 2

        # Outline keeps the text readable on any background.
        self.draw_outlined_text(
            win=win,
            text_str=text_str,
            pos=(x, y),
            font=font,
            text_colour=Colours.WHITE,
            outline_colour=Colours.BLACK,
            thickness=4,
        )

    # =========================
    # OUTLINED TEXT (helper)
    # =========================
    def draw_outlined_text(
        self,
        win: pygame.Surface,
        text_str: str,
        pos: Tuple[int, int],
        font: pygame.font.Font,
        text_colour=Colours.WHITE,
        outline_colour=Colours.BLACK,
        thickness: int = 2,
    ) -> None:
        """
        Draws text with an outline.

        The outline is rendered by drawing the same text several times slightly
        offset, then drawing the main text on top.

        Args:
            win: The target surface.
            text_str: The text to render.
            pos: Top-left pixel position for the rendered text.
            font: Pygame font to use.
            text_colour: Fill colour.
            outline_colour: Outline colour.
            thickness: Offset distance in pixels for the outline.
        """
        x, y = pos

        # Outline pass (skip the centre offset; that's the fill pass).
        for dx in (-thickness, 0, thickness):
            for dy in (-thickness, 0, thickness):
                if dx == 0 and dy == 0:
                    continue
                outline_surface = font.render(text_str, True, outline_colour)
                win.blit(outline_surface, (x + dx, y + dy))

        # Fill pass.
        text_surface = font.render(text_str, True, text_colour)
        win.blit(text_surface, (x, y))

    # =========================
    # HEALTH BAR
    # =========================
    def draw_health_bar(
        self,
        win: pygame.Surface,
        x: int,
        y: int,
        health: int,
        label: str,
        align: str = "left",
        team_colour=Colours.WHITE,
        max_health: int = 100,
        role_indicator: Optional[
            Union[
                Tuple[str, Tuple[int, int, int]],                 # old: ("[V]", colour)
                Sequence[Tuple[str, Tuple[int, int, int]]],       # new: [("[V]", colour), ("[S]", colour)]
            ]
        ] = None,
    ) -> None:
        """
        Draws a semi-transparent health bar and a labelled readout above it.

        The label supports optional multi-colour "role / item" tags (e.g. [V], [S]).
        These tags are rendered first, then the player's name + current health.

        Args:
            win: The target surface.
            x, y: Bar position. For align="left" this is the left edge.
                 For align="right" this is treated as the right edge.
            health: Current health value.
            label: Player name / label.
            align: "left" or "right" alignment.
            team_colour: Colour used for the filled portion of the bar.
            max_health: Health value representing a full bar.
            role_indicator: Optional role/item tag(s). Accepts either:
                - ("[V]", colour)  (legacy)
                - [("[V]", colour), ("[S]", colour), ...] (preferred)
        """
        max_width = 200
        height = 20

        # Avoid division by zero and clamp the fill width.
        if max_health > 0:
            fill_ratio = max(0.0, min(1.0, health / max_health))
        else:
            fill_ratio = 0.0

        filled_width = int(max_width * fill_ratio)

        # Background (dark red, translucent).
        bar_surf = pygame.Surface((max_width, height), pygame.SRCALPHA)
        bar_surf.fill((150, 0, 0, 150))

        # Fill (team colour, translucent).
        fill_surf = pygame.Surface((filled_width, height), pygame.SRCALPHA)
        fill_surf.fill(team_colour + (180,))

        # Position the bar (support right alignment for symmetry on HUD).
        bg_rect = pygame.Rect(x, y, max_width, height)
        if align == "right":
            bg_rect.right = x

        win.blit(bar_surf, (bg_rect.x, bg_rect.y))
        win.blit(fill_surf, (bg_rect.x, bg_rect.y))

        # ---- Label text above the bar ----
        label_str = f"{label}: {health}"
        label_w = self.fonts.HEALTH_FONT.size(label_str)[0]

        # Normalise role indicators into a list of (text, colour) segments.
        segments: Sequence[Tuple[str, Tuple[int, int, int]]] = []
        if role_indicator:
            # Backwards compatible:
            # - old format: ("[V]", colour)
            # - new format: [("[V]", colour), ("[S]", colour), ...]
            if isinstance(role_indicator, tuple):
                segments = [role_indicator]
            else:
                segments = role_indicator

        # Calculate total width for alignment when rendering to the right.
        role_w = sum(self.fonts.HEALTH_FONT.size(text + " ")[0] for text, _ in segments)
        total_w = role_w + label_w

        # Place the label line above the bar.
        label_pos = (
            (bg_rect.left, y - 25) if align == "left"
            else (bg_rect.right - total_w, y - 25)
        )

        # Draw role/item indicators first, each with its own colour.
        if segments:
            for text, colour in segments:
                self.draw_outlined_text(
                    win=win,
                    text_str=text + " ",
                    pos=label_pos,
                    font=self.fonts.HEALTH_FONT,
                    text_colour=colour,
                    outline_colour=Colours.BLACK,
                    thickness=1,
                )
                label_pos = (
                    label_pos[0] + self.fonts.HEALTH_FONT.size(text + " ")[0],
                    label_pos[1],
                )

        # Draw the main label (name + health) in white.
        self.draw_outlined_text(
            win=win,
            text_str=label_str,
            pos=label_pos,
            font=self.fonts.HEALTH_FONT,
            text_colour=Colours.WHITE,
            outline_colour=Colours.BLACK,
            thickness=1,
        )

    # =========================
    # GAME TITLE (watermark)
    # =========================
    def draw_game_title(self, win: pygame.Surface) -> None:
        """
        Draws a faint 'FOLLOWERFEUDS' watermark centred in the playfield.

        The playfield is the area below the UI bar, so the watermark does not
        clash with the HUD.
        """
        title_surface = self.fonts.GAME_TITLE_FONT.render("FOLLOWERFEUDS", True, Colours.GREY)

        # Centre in the playfield area (below the UI bar).
        playfield_height = self.config.HEIGHT - self.config.UI_BAR_HEIGHT
        play_centre_y = self.config.UI_BAR_HEIGHT + playfield_height // 2
        title_rect = title_surface.get_rect(center=(self.config.WIDTH // 2, play_centre_y))

        # Alpha for watermark effect (higher alpha = more visible).
        title_surface.set_alpha(80)
        win.blit(title_surface, title_rect)

    # =========================
    # MATCH CLOCK (UI bar centre)
    # =========================
    def draw_match_clock(self, win: pygame.Surface, elapsed_ms: int) -> None:
        """
        Draws the match clock centred in the UI bar.

        Format: MM:SS.t (tenths of a second)

        Args:
            win: The target surface.
            elapsed_ms: Elapsed time in milliseconds.
        """
        total_seconds = max(0, elapsed_ms) / 1000.0
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        tenths = int((total_seconds * 10) % 10)

        clock_str = f"{minutes:02d}:{seconds:02d}.{tenths}"
        font = self.fonts.FONT  # Same font as countdown for a consistent HUD style.

        text_w, text_h = font.size(clock_str)
        x = (self.config.WIDTH - text_w) // 2
        y = (self.config.UI_BAR_HEIGHT - text_h) // 2

        self.draw_outlined_text(
            win=win,
            text_str=clock_str,
            pos=(x, y),
            font=font,
            text_colour=Colours.WHITE,
            outline_colour=Colours.BLACK,
            thickness=3,
        )