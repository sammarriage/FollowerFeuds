from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class GameState(Enum):
    """High-level states that control the match flow and UI."""
    WHEEL_SPIN = "wheel_spin"
    VS_SCREEN = "vs_screen"
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    DELAYED_VICTORY = "delayed_victory"
    GAME_OVER = "game_over"


class SpecialRole(Enum):
    """
    Optional per-player modifiers.
    Stored as single-character codes because that's what the setup prompt uses.
    """
    NONE = "N"
    TITAN = "T"
    VENOM = "V"
    GLITCH = "G"
    CLONE = "C"


@dataclass
class GameConfig:
    """
    Central configuration object for the game.

    Notes:
    - This dataclass currently *interactively* asks for team sizes and roles on creation.
      That keeps setup simple for local runs, but it does mean instantiating GameConfig()
      will block waiting for user input.
    - After team setup, we adjust spinner/UI sizing and parse player names.
    """

    # =========================
    # PLAYER NAMES
    # =========================
    # Expected format: "DisplayName (@handle) DisplayName2 (@handle2) ..."
    # The parser groups tokens until it sees something ending in ')'.
    NAMES_STRING: str = "Player 1"

    SPINNER1_NAME: str = ""
    SPINNER2_NAME: str = ""
    SPINNER3_NAME: str = ""
    SPINNER4_NAME: str = ""
    SPINNER5_NAME: str = ""
    SPINNER6_NAME: str = ""

    # =========================
    # TEAM CONFIGURATION
    # =========================
    TEAM_A_SIZE: int = 0
    TEAM_B_SIZE: int = 0

    # Use default_factory to avoid shared mutable defaults between instances.
    TEAM_A_ROLES: List[SpecialRole] = field(default_factory=list)
    TEAM_B_ROLES: List[SpecialRole] = field(default_factory=list)

    # =========================
    # WINDOW / UI
    # =========================
    # UI_BAR_HEIGHT is recalculated based on how many player rows are needed.
    UI_BAR_HEIGHT: int = 150
    WIDTH: int = 1280
    HEIGHT: int = 720
    FPS: int = 60

    # =========================
    # SPINNER SETTINGS
    # =========================
    SPINNER_RADIUS: int = 110
    SPINNER_SPEED: int = 7
    SPINNER_MASS: int = 3

    # =========================
    # ITEM TIMINGS (ms)
    # =========================
    SHIELD_DURATION: int = 5000
    DAGGER_DURATION: int = 7000

    HEALTH_SPAWN_DELAY: int = 5000
    HEALTH_RESPAWN_DELAY: int = 20000
    DAGGER_SPAWN_DELAY: int = 8000
    DAGGER_RESPAWN_DELAY: int = 20000
    SHIELD_SPAWN_DELAY: int = 10000
    SHIELD_RESPAWN_DELAY: int = 25000

    # =========================
    # MATCH FLOW
    # =========================
    COUNTDOWN_TIME: int = 3
    VS_DISPLAY_TIME: int = 1500

    # =========================
    # ASSETS
    # =========================
    IMAGES_FOLDER: str = r"Desktop"

    PFP1_JPG_PATH: str = "pfp1.jpeg"
    PFP2_JPG_PATH: str = "pfp2.jpeg"
    PFP3_JPG_PATH: str = "pfp3.jpeg"
    PFP4_JPG_PATH: str = "pfp4.jpeg"
    PFP5_JPG_PATH: str = "pfp5.jpeg"
    PFP6_JPG_PATH: str = "pfp6.jpeg"

    # =========================
    # SOUND PATHS
    # =========================
    SHIELD_EQUIP_SOUND_PATH: str = "ShieldEquip.mp3"
    SHIELD_HIT_SOUND_PATH: str = "ShieldHit.mp3"
    DAGGER_EQUIP_SOUND_PATH: str = "DaggerEquip.mp3"
    DAGGER_HIT_SOUND_PATH: str = "DaggerHit.mp3"
    HEALTH_EQUIP_SOUND_PATH: str = "HealthEquip.mp3"
    REGULAR_HIT_SOUND_PATH: str = "RegularHit.mp3"
    GLITCH_SOUND_PATH: str = "glitch.mp3"
    NOSHIELD_SOUND_PATH: str = "noshield.mp3"
    CLONE_SOUND_PATH: str = "clone.mp3"

    # =========================
    # SOUND SETTINGS
    # =========================
    SOUND_VOLUME: float = 0.3
    NOSHIELD_SOUND_VOLUME: float = 1.0
    GLITCH_SOUND_COOLDOWN: int = 500

    # =========================
    # INITIALISATION
    # =========================
    def __post_init__(self) -> None:
        """
        Run interactive setup and then compute any dependent configuration.

        Ordering matters:
        1) Team sizes & roles must be known before UI sizing (clone roles add rows).
        2) Spinner size depends on total players.
        3) Names can be parsed at any time, but we do it last to keep console output tidy.
        """
        self._get_team_sizes_and_roles()
        self._adjust_spinner_size()
        self._adjust_ui_bar_height()
        self._separate_names()

    # =========================
    # TEAM SETUP (interactive)
    # =========================
    def _get_team_sizes_and_roles(self) -> None:
        """Ask the user for team sizes and special roles via the console."""
        print("\n" + "=" * 50)
        print("FOLLOWER FEUDS - TEAM SETUP")
        print("=" * 50)
        print("Choose team sizes (1–3 players per team):")

        self.TEAM_A_SIZE = self._prompt_team_size(team_name="Team A (left side)")
        self.TEAM_B_SIZE = self._prompt_team_size(team_name="Team B (right side)")

        print(f"\nTeam A: {self.TEAM_A_SIZE} player(s)")
        print(f"Team B: {self.TEAM_B_SIZE} player(s)")
        print(f"Total: {self.TEAM_A_SIZE + self.TEAM_B_SIZE} players")

        print("\n" + "=" * 50)
        print("SPECIAL ROLES SELECTION")
        print("=" * 50)
        print("T - Titan")
        print("V - Venom")
        print("G - Glitch")
        print("C - Clone")
        print("N - None")
        print("=" * 50)

        # Clear in case this object is reused (or if values were pre-set).
        self.TEAM_A_ROLES.clear()
        self.TEAM_B_ROLES.clear()

        self.TEAM_A_ROLES.extend(self._prompt_roles(team_label="Team A", count=self.TEAM_A_SIZE))
        self.TEAM_B_ROLES.extend(self._prompt_roles(team_label="Team B", count=self.TEAM_B_SIZE))

    def _prompt_team_size(self, team_name: str) -> int:
        """Prompt until the user enters a valid team size (1–3)."""
        while True:
            try:
                print(f"\n{team_name}:")
                size = int(input("Enter number of players (1–3): "))
                if 1 <= size <= 3:
                    return size
            except ValueError:
                # Non-integer input — just re-prompt.
                pass

    def _prompt_roles(self, team_label: str, count: int) -> List[SpecialRole]:
        """Prompt roles for each player in a team, returning a list of SpecialRole."""
        roles: List[SpecialRole] = []
        print(f"\n{team_label} Roles ({count} players):")

        valid_codes = {"T", "V", "G", "C", "N"}
        for i in range(count):
            while True:
                code = input(f"Player {i + 1} role (T/V/G/C/N): ").strip().upper()
                if code in valid_codes:
                    roles.append(SpecialRole(code))
                    break

        return roles

    # =========================
    # ADJUSTMENTS
    # =========================
    def _adjust_spinner_size(self) -> None:
        """
        Adjust the spinner radius based on player count.

        The smaller radius helps prevent constant overlaps when there are more spinners.
        """
        total = self.TEAM_A_SIZE + self.TEAM_B_SIZE

        if total >= 4 or self.TEAM_A_SIZE == 3 or self.TEAM_B_SIZE == 3:
            self.SPINNER_RADIUS = 90
            print("Using smaller spinner size (90) for better gameplay")
        else:
            self.SPINNER_RADIUS = 110
            print("Using standard spinner size (110)")

    def _adjust_ui_bar_height(self) -> None:
        """
        Resize the UI bar height based on how many rows we need to display.

        Clone roles effectively add additional 'slots' (extra rows), so we include them in
        the row count and choose a UI height that fits while staying within sensible limits.
        """
        clone_slots_a = sum(1 for r in self.TEAM_A_ROLES if r == SpecialRole.CLONE)
        clone_slots_b = sum(1 for r in self.TEAM_B_ROLES if r == SpecialRole.CLONE)

        rows_a = self.TEAM_A_SIZE + clone_slots_a
        rows_b = self.TEAM_B_SIZE + clone_slots_b
        max_rows = max(rows_a, rows_b)

        # Layout constants for the UI rows.
        start_y = 35
        spacing = 40
        bottom_margin = 40 if max_rows >= 2 else 20

        needed = start_y + (max_rows - 1) * spacing + bottom_margin

        # Clamp UI height so it doesn't get silly.
        self.UI_BAR_HEIGHT = max(70, min(needed, 260))

        # The game window height includes the UI bar height.
        self.HEIGHT = 720 + self.UI_BAR_HEIGHT

    # =========================
    # NAME PARSING
    # =========================
    def _separate_names(self) -> None:
        """
        Parse NAMES_STRING into up to 6 spinner names.

        The simple rule here: tokens are grouped until we see a token that ends with ')'.
        That works well for names in the form: "Name (@handle)".
        """
        if not self.NAMES_STRING:
            return

        names: List[str] = []
        current: List[str] = []

        for part in self.NAMES_STRING.strip().split():
            current.append(part)
            if part.endswith(")"):
                names.append(" ".join(current))
                current.clear()

        # If the string didn't end cleanly (no trailing ')'), keep whatever we collected.
        if current:
            names.append(" ".join(current))

        print(f"Parsed names: {names}")
        print(f"Number of names found: {len(names)}")

        targets = [
            "SPINNER1_NAME",
            "SPINNER2_NAME",
            "SPINNER3_NAME",
            "SPINNER4_NAME",
            "SPINNER5_NAME",
            "SPINNER6_NAME",
        ]

        # Fill from parsed names (up to 6).
        for i, name in enumerate(names[:6]):
            setattr(self, targets[i], name)

        # Fill any remaining slots with defaults.
        for i in range(len(names), 6):
            setattr(self, targets[i], f"Player {i + 1}")