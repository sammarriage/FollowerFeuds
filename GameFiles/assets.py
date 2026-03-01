import os
import sys
import io
from typing import Dict

import pygame
from PIL import Image, ImageDraw

from constants import Colours
from config import GameConfig


class AssetManager:
    """
    Loads and stores image + sound assets, with support for both:
      - normal development runs (project folder structure)
      - PyInstaller builds (temporary extraction folder via sys._MEIPASS)

    Notes on folder structure assumptions:
      - Images (e.g., profile pictures) live under config.IMAGES_FOLDER
      - Sound files typically live under a top-level "SoundEffects" folder
    """

    def __init__(self, config: GameConfig):
        self.config = config

        # Loaded assets (pygame surfaces and mixer sounds)
        self.images: Dict[str, pygame.Surface] = {}
        self.sounds: Dict[str, pygame.mixer.Sound | None] = {}

        # Glitch sound throttling (to prevent audio spam)
        self.last_glitch_sound_time = 0
        self.glitch_sound_cooldown = self.config.GLITCH_SOUND_COOLDOWN

        self._load_assets()

    # =========================
    # PATH RESOLUTION
    # =========================
    def get_resource_path(self, relative_path: str) -> str:
        """
        Convert a project-relative path into an absolute filesystem path.

        Why this exists:
          - In PyInstaller builds, files are extracted to a temp directory and the root
            is available as sys._MEIPASS.
          - In development, we resolve relative to this file, and handle the common case
            where this module is inside a "GameFiles" folder but assets sit one level up.
        """
        # PyInstaller provides sys._MEIPASS at runtime (attribute may not exist in dev).
        base_path = getattr(sys, "_MEIPASS", None)

        if base_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # If this file lives in GameFiles, jump up one folder so SoundEffects is found.
            if os.path.basename(current_dir) == "GameFiles":
                base_path = os.path.abspath(os.path.join(current_dir, ".."))
            else:
                base_path = current_dir

        return os.path.join(base_path, relative_path)

    # =========================
    # LOAD ALL ASSETS
    # =========================
    def _load_assets(self) -> None:
        """Entry point for loading everything the game needs."""
        self._load_images()
        self._load_sounds()

    # =========================
    # IMAGES
    # =========================
    def _load_images(self) -> None:
        """
        Load profile pictures and convert them into circular, alpha-masked pygame surfaces.

        If an image is missing (or loading fails), we fall back to a coloured circle so the
        game remains playable rather than crashing on startup.
        """
        try:
            # Base folder for profile picture downloads.
            # config.IMAGES_FOLDER should be a folder name or relative path.
            base_folder = self.get_resource_path(self.config.IMAGES_FOLDER)

            # Individual file names/relative paths as defined by config.
            pfp_paths = [
                self.config.PFP1_JPG_PATH,
                self.config.PFP2_JPG_PATH,
                self.config.PFP3_JPG_PATH,
                self.config.PFP4_JPG_PATH,
                self.config.PFP5_JPG_PATH,
                self.config.PFP6_JPG_PATH,
            ]

            for i, rel_path in enumerate(pfp_paths, start=1):
                full_path = os.path.join(base_folder, rel_path)

                if os.path.exists(full_path):
                    self.images[f"pfp{i}"] = self._load_and_convert_circular_image(
                        full_path,
                        self.config.SPINNER_RADIUS,
                    )
                else:
                    # Missing image: create a simple coloured placeholder.
                    self._create_single_fallback(f"pfp{i}", i - 1)

        except Exception as exc:
            # Broad catch here is intentional: asset loading is non-critical
            # (we prefer graceful fallback rather than hard failure).
            print(f"Error loading profile images: {exc}")
            self._create_fallback_images()

    def _load_and_convert_circular_image(self, jpg_path: str, radius: int) -> pygame.Surface:
        """
        Load an image from disk, resize it to a square diameter, and apply a circular alpha mask.

        Returns:
            pygame.Surface with per-pixel alpha (convert_alpha()) suitable for blitting.
        """
        diameter = radius * 2

        # PIL handles resizing/masking cleanly; pygame then loads from an in-memory PNG.
        img = Image.open(jpg_path).convert("RGBA")
        img = img.resize((diameter, diameter), Image.LANCZOS)

        # Create a circular mask (L mode = greyscale) and apply as alpha.
        mask = Image.new("L", (diameter, diameter), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, diameter, diameter), fill=255)
        img.putalpha(mask)

        # Convert PIL image -> bytes -> pygame surface (no need to save to disk).
        byte_stream = io.BytesIO()
        img.save(byte_stream, format="PNG")
        byte_stream.seek(0)

        return pygame.image.load(byte_stream).convert_alpha()

    def _create_single_fallback(self, key: str, colour_index: int) -> None:
        """
        Create a simple coloured circle surface as a fallback image.

        Args:
            key: The dictionary key to store under (e.g., "pfp1")
            colour_index: Used to pick a deterministic colour per player.
        """
        colours = [
            Colours.BLUE,
            Colours.RED,
            Colours.ORANGE,
            Colours.PURPLE,
            Colours.GREEN,
            Colours.YELLOW,
        ]
        colour = colours[colour_index % len(colours)]

        diameter = self.config.SPINNER_RADIUS * 2
        surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)

        pygame.draw.circle(
            surf,
            colour,
            (self.config.SPINNER_RADIUS, self.config.SPINNER_RADIUS),
            self.config.SPINNER_RADIUS,
        )

        self.images[key] = surf

    def _create_fallback_images(self) -> None:
        """Generate placeholder images for all six profile picture slots."""
        for i in range(1, 7):
            self._create_single_fallback(f"pfp{i}", i - 1)

    # =========================
    # SOUNDS
    # =========================
    def _load_sounds(self) -> None:
        """
        Load all sound effects into pygame.mixer.Sound objects.

        Path handling:
          - First tries: base/SoundEffects/<filename>
          - If that fails: base/<rel_path> (lets config provide a full relative path)
        """
        sound_paths = {
            "shield_equip": self.config.SHIELD_EQUIP_SOUND_PATH,
            "shield_hit": self.config.SHIELD_HIT_SOUND_PATH,
            "dagger_equip": self.config.DAGGER_EQUIP_SOUND_PATH,
            "dagger_hit": self.config.DAGGER_HIT_SOUND_PATH,
            "health_equip": self.config.HEALTH_EQUIP_SOUND_PATH,
            "regular_hit": self.config.REGULAR_HIT_SOUND_PATH,
            "glitch": self.config.GLITCH_SOUND_PATH,
            "noshield": self.config.NOSHIELD_SOUND_PATH,
            "clone": self.config.CLONE_SOUND_PATH,
        }

        for name, rel_path in sound_paths.items():
            full_path = None

            try:
                # Preferred layout: SoundEffects folder at the base.
                full_path = self.get_resource_path(os.path.join("SoundEffects", rel_path))

                # If config already includes a path (or project layout differs), try raw rel_path too.
                if not os.path.exists(full_path):
                    full_path = self.get_resource_path(rel_path)

                if not os.path.exists(full_path):
                    raise FileNotFoundError(f"Sound file not found: {full_path}")

                sound = pygame.mixer.Sound(full_path)

                # Per-sound volume overrides (everything else uses the global default).
                if name == "noshield":
                    sound.set_volume(self.config.NOSHIELD_SOUND_VOLUME)
                else:
                    sound.set_volume(self.config.SOUND_VOLUME)

                self.sounds[name] = sound

            except (pygame.error, FileNotFoundError) as exc:
                # Keep the game running even if audio is missing/broken.
                print(f"Error loading sound '{name}' at {full_path}: {exc}")
                self.sounds[name] = None

    # =========================
    # PLAY SOUND
    # =========================
    def play_sound(self, sound_name: str) -> None:
        """
        Play a named sound if it exists.

        Special case:
          - "glitch" is rate-limited using GLITCH_SOUND_COOLDOWN to avoid repeated triggers
            becoming annoying or clipping.
        """
        sound = self.sounds.get(sound_name)
        if sound is None:
            return

        now_ms = pygame.time.get_ticks()

        if sound_name == "glitch":
            if now_ms - self.last_glitch_sound_time < self.glitch_sound_cooldown:
                return
            self.last_glitch_sound_time = now_ms

        sound.play()