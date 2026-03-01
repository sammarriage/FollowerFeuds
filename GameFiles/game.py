import pygame
import math
from typing import List, Optional, Dict, Any

from config import GameConfig, GameState, SpecialRole
from constants import Colours
from assets import AssetManager
from spinner import Spinner
from items import HealthPack, DaggerItem, ShieldItem
from obstacles import CornerObstacle
from collision import CollisionManager
from renderer import Renderer
from wheelSpin import Wheel, WheelSpinner


class Game:
    """
    Top-level game controller.

    Responsibilities:
    - Initialising pygame and core game systems (assets, renderer, clock)
    - Managing the game state machine (VS screen -> countdown -> playing -> game over)
    - Updating gameplay objects (spinners, items, collisions, obstacles)
    - Drawing everything to the window each frame
    """

    def __init__(self):
        pygame.init()
        self.config = GameConfig()

        # The playable area excludes the UI bar at the top.
        self.playfield = pygame.Rect(
            0,
            self.config.UI_BAR_HEIGHT,
            self.config.WIDTH,
            self.config.HEIGHT - self.config.UI_BAR_HEIGHT
        )

        self.win = pygame.display.set_mode((self.config.WIDTH, self.config.HEIGHT))
        pygame.display.set_caption("Follower Feuds")

        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self.config)
        self.asset_manager = AssetManager(self.config)

        # State machine control
        self.game_state = GameState.WHEEL_SPIN
        self.vs_start_time = pygame.time.get_ticks()
        self.last_time = pygame.time.get_ticks()  # Used for 1-second countdown ticks
        self.countdown = self.config.COUNTDOWN_TIME

        # Match clock: starts on GO!, freezes when the match ends.
        self.match_start_time: Optional[int] = None
        self.match_end_time: Optional[int] = None

        # End-of-match console output guard.
        self.results_printed = False

        # --------------------------------------------------
        # WHEEL SPIN
        # --------------------------------------------------
        spinner_names = [
            name for name in [
                self.config.SPINNER1_NAME,
                self.config.SPINNER2_NAME,
                self.config.SPINNER3_NAME,
                self.config.SPINNER4_NAME,
                self.config.SPINNER5_NAME,
                self.config.SPINNER6_NAME,
            ] if name
        ]
        self.wheel = Wheel(spinner_names, radius=300)
        self.wheel_spinner = WheelSpinner(self.wheel)

        # Initialise spinners, items, and obstacles.
        self._initialise_game_objects()

    # --------------------------------------------------
    # INITIAL SETUP
    # --------------------------------------------------

    def _initialise_game_objects(self):
        """Create and position all gameplay objects for a new match."""
        self.all_spinners: List[Spinner] = []

        # Pre-calculate useful Y positions
        mid_y = self.playfield.top + self.playfield.height // 2
        one_third_y = self.playfield.top + self.playfield.height // 3
        two_third_y = self.playfield.top + 2 * self.playfield.height // 3
        one_fifth_y = self.playfield.top + self.playfield.height // 5
        four_fifth_y = self.playfield.top + 4 * self.playfield.height // 5

        # Choose vertical spawn spread based on team size:
        # 1 player  -> middle
        # 2 players -> 1/3 and 2/3
        # 3 players -> middle + 1/5 and 4/5 (your current preference)
        def _team_positions(team_x: int, team_size: int):
            if team_size == 1:
                ys = [mid_y]
            elif team_size == 2:
                ys = [one_third_y, two_third_y]
            else:
                ys = [mid_y, one_fifth_y, four_fifth_y]
            return [(team_x, y) for y in ys]

        # Team A spawns on the left quarter of the arena.
        team_a_x = self.config.WIDTH // 4
        team_a_positions = _team_positions(team_a_x, self.config.TEAM_A_SIZE)

        # Team B spawns on the right quarter of the arena.
        team_b_x = self.config.WIDTH - self.config.WIDTH // 4
        team_b_positions = _team_positions(team_b_x, self.config.TEAM_B_SIZE)

        # Assets/names are assumed to be provided in the correct order for the spinners.
        all_images = list(self.asset_manager.images.values())
        all_names = [
            self.config.SPINNER1_NAME,
            self.config.SPINNER2_NAME,
            self.config.SPINNER3_NAME,
            self.config.SPINNER4_NAME,
            self.config.SPINNER5_NAME,
            self.config.SPINNER6_NAME
        ]

        # Build Team A
        for i in range(self.config.TEAM_A_SIZE):
            spinner = Spinner(
                *team_a_positions[i],
                all_images[i],
                self.config.SPINNER_SPEED,
                self.config.SPINNER_MASS,
                all_names[i],
                "TeamA",
                self.config.SPINNER_RADIUS,
                self.config.TEAM_A_ROLES[i]
            )
            self.all_spinners.append(spinner)

        # Build Team B (offset by Team A size)
        offset = self.config.TEAM_A_SIZE
        for i in range(self.config.TEAM_B_SIZE):
            spinner = Spinner(
                *team_b_positions[i],
                all_images[offset + i],
                self.config.SPINNER_SPEED,
                self.config.SPINNER_MASS,
                all_names[offset + i],
                "TeamB",
                self.config.SPINNER_RADIUS,
                self.config.TEAM_B_ROLES[i]
            )
            self.all_spinners.append(spinner)

        # Useful reference for momentum balancing (depends on your CollisionManager implementation).
        self.initial_speed_total = sum(s.speed for s in self.all_spinners)

        # Spawnable items (they manage their own timers/activation).
        self.health_pack = HealthPack(self.config)
        self.dagger_item = DaggerItem(self.config)
        self.shield_item = ShieldItem(self.config)

        # Corner obstacles define the arena boundaries/shape.
        self.corner_obstacles = [
            CornerObstacle("topleft", self.playfield),
            CornerObstacle("topright", self.playfield),
            CornerObstacle("bottomleft", self.playfield),
            CornerObstacle("bottomright", self.playfield)
        ]

    # --------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------

    def run(self):
        """Main loop: handle events, update state, render frame."""
        running = True
        while running:
            # Cap frame rate for consistent simulation.
            self.clock.tick(self.config.FPS)

            # Basic event handling (quit only).
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            self._update()
            self._render()
            pygame.display.update()

        pygame.quit()

    # --------------------------------------------------
    # UPDATE LOGIC
    # --------------------------------------------------

    def _update(self):
        """Advance the game simulation based on the current state."""
        now = pygame.time.get_ticks()

        # -------------------------------
        # WHEEL SPIN STATE  ← ADDED
        # -------------------------------
        if self.game_state == GameState.WHEEL_SPIN:
            dt = self.clock.get_time() / 1000.0
            self.wheel_spinner.update(dt)

            if not self.wheel_spinner.active:
                self.game_state = GameState.VS_SCREEN
                self.vs_start_time = now
            return

        if self.game_state == GameState.VS_SCREEN:
            if now - self.vs_start_time > self.config.VS_DISPLAY_TIME:
                self.game_state = GameState.COUNTDOWN
                self.last_time = now

        elif self.game_state == GameState.COUNTDOWN:
            if (now - self.last_time) >= 1000:
                self.countdown -= 1
                self.last_time = now

            if self.countdown < 0:
                self.game_state = GameState.PLAYING
                self.match_start_time = now
                for s in self.all_spinners:
                    s.start_moving()

        elif self.game_state == GameState.PLAYING:
            self._update_playing_state()

            alive = [s for s in self.all_spinners if s.health > 0]
            team_a = [s for s in alive if s.team == "TeamA"]
            team_b = [s for s in alive if s.team == "TeamB"]

            if not team_a or not team_b:
                self.game_state = (
                    GameState.DELAYED_VICTORY
                    if self._check_for_delayed_victory()
                    else GameState.GAME_OVER
                )
                self.match_end_time = now

        elif self.game_state == GameState.DELAYED_VICTORY:
            self._update_delayed_victory_state()

    def _update_playing_state(self):
        """
        Update everything in the main gameplay state:
        - movement
        - collisions (spinner-spinner and spinner-obstacle)
        - role abilities
        - momentum maintenance
        - item spawns/pickups
        """
        active = [s for s in self.all_spinners if s.health > 0]

        for s in active:
            s.move(self.playfield)

        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                CollisionManager.handle_spinner_collision(
                    active[i], active[j], self.asset_manager
                )

        for s in active:
            s.check_phasing_completion(self.all_spinners, self.asset_manager)
            if s.role == SpecialRole.CLONE:
                s.create_clone(self)

        for s in active:
            for o in self.corner_obstacles:
                o.collide_with_spinner(s)

        CollisionManager.maintain_game_momentum(self.all_spinners)
        self._update_items(active)

    def _consume_item(self, item, sound_key: str) -> None:
        """Deactivate item, schedule respawn, play sound."""
        now = pygame.time.get_ticks()
        item.active = False
        item.spawn_time = now
        self.asset_manager.play_sound(sound_key)

    def _update_items(self, active: List[Spinner]):
        """
        Update item timers/spawns and apply effects when a spinner collects them.
        """
        self.health_pack.update(self.playfield)
        self.dagger_item.update(self.playfield)
        self.shield_item.update(self.playfield)

        now = pygame.time.get_ticks()

        for s in active:
            if self.health_pack.check_collision(s):
                max_hp = 130 if s.role == SpecialRole.TITAN else 100
                s.health = min(max_hp, s.health + 5)
                s.add_heal_text(5)
                s.heal = True
                s.heal_end_time = now + 450
                self._consume_item(self.health_pack, "health_equip")

            if self.dagger_item.check_collision(s) and not s.carrying_dagger:
                s.carrying_dagger = True
                s.dagger_end_time = now + self.config.DAGGER_DURATION
                self._consume_item(self.dagger_item, "dagger_equip")

            if self.shield_item.check_collision(s) and not s.shield and s.role != SpecialRole.TITAN:
                s.shield = True
                s.shield_end_time = now + self.config.SHIELD_DURATION
                self._consume_item(self.shield_item, "shield_equip")

    def _aggregate_clone_stats(self) -> List[Dict[str, Any]]:
        """
        Combine original + clone damage and health into a single stat line.
        Returns a list of dicts: { "name", "team", "damage", "health" } sorted by (damage + health) descending.
        """
        combined: Dict[str, Dict[str, Any]] = {}

        for s in self.all_spinners:
            base_name = s.name.split(" Clone")[0]

            if base_name not in combined:
                combined[base_name] = {
                    "name": base_name,
                    "team": s.team,
                    "damage": 0,
                    "health": 0
                }

            combined[base_name]["damage"] += getattr(s, "damage_dealt", 0)
            combined[base_name]["health"] += max(0, getattr(s, "health", 0))

        return sorted(
            combined.values(),
            key=lambda d: (d["damage"] + d["health"], d["damage"], d["health"]),
            reverse=True
        )

    # --------------------------------------------------
    # RENDERING
    # --------------------------------------------------

    def _render(self):
        """Draw a full frame based on the current game state."""

        # -------------------------------
        # WHEEL SPIN RENDER  ← ADDED
        # -------------------------------
        if self.game_state == GameState.WHEEL_SPIN:
            self.win.fill(Colours.BLACK)
            self.wheel.draw(
                self.win,
                self.renderer.fonts.HEALTH_FONT,
                self.renderer.fonts.HEALTH_FONT
            )
            return

        self.win.fill(Colours.BLACK)

        # UI bar background (top strip).
        pygame.draw.rect(
            self.win,
            Colours.BLACK,
            (0, 0, self.config.WIDTH, self.config.UI_BAR_HEIGHT)
        )

        # Separator line between UI and playfield.
        pygame.draw.line(
            self.win,
            Colours.WHITE,
            (0, self.config.UI_BAR_HEIGHT),
            (self.config.WIDTH, self.config.UI_BAR_HEIGHT),
            1
        )

        # Match clock:
        # - shows only after GO!
        # - freezes when game ends (match_end_time set)
        if self.match_start_time is not None:
            now = pygame.time.get_ticks()
            end = self.match_end_time or now
            self.renderer.draw_match_clock(
                self.win, max(0, end - self.match_start_time)
            )

        if self.game_state == GameState.COUNTDOWN:
            self._render_match_scene(draw_countdown=True)
        elif self.game_state == GameState.PLAYING:
            self._render_match_scene()
        elif self.game_state == GameState.GAME_OVER:
            self._render_game_over()
        elif self.game_state == GameState.DELAYED_VICTORY:
            self._render_delayed_victory()

    def _render_match_scene(self, draw_countdown: bool = False) -> None:
        """
        Draw the shared match scene: obstacles, watermark, items, spinners, health bars.
        Optionally overlay the countdown text on top (for pre-match countdown).
        """
        for o in self.corner_obstacles:
            o.draw(self.win)

        self.renderer.draw_game_title(self.win)

        self.health_pack.draw(self.win)
        self.dagger_item.draw(self.win)
        self.shield_item.draw(self.win)

        for s in self.all_spinners:
            if s.health > 0:
                s.draw(self.win, self.renderer.fonts)

        self._draw_health_bars()

        if draw_countdown:
            self.renderer.draw_countdown(self.win, self.countdown, self.playfield.center)

    # --------------------------------------------------
    # GAME OVER (FULL)
    # --------------------------------------------------

    def _render_game_over(self):
        """
        Draw the final match view plus a winner banner.
        The match clock will be frozen by match_end_time.
        """
        # Freeze clock the first time we enter GAME_OVER.
        if self.match_end_time is None:
            self.match_end_time = pygame.time.get_ticks()

        # Let poison ticks finish resolving even after the win condition is met.
        # (This keeps damage totals accurate and prevents poison from “hanging”.)
        for s in self.all_spinners:
            if getattr(s, "poison_ticks", 0) > 0:
                # Spinner handles tick timing internally.
                s._update_status_effects()

        # Print final damage results once poison has fully resolved.
        if not self.results_printed:
            any_poison_active = any(getattr(s, "poison_ticks", 0) > 0 for s in self.all_spinners)
            if not any_poison_active:
                print("\n=== DAMAGE RESULTS ===")
                for s in sorted(
                    self.all_spinners,
                    key=lambda s: s.damage_dealt + s.health,
                    reverse=True,
                ):
                    print(
                        f"{s.name} (Team: {s.team}) - Damage Dealt: {s.damage_dealt}, Final Health: {s.health}"
                    )
                self.results_printed = True

        # Arena / obstacles / watermark.
        for o in self.corner_obstacles:
            o.draw(self.win)

        self.renderer.draw_game_title(self.win)

        # Keep items visible on the final screen (matches old behaviour).
        self.health_pack.draw(self.win)
        self.dagger_item.draw(self.win)
        self.shield_item.draw(self.win)

        # Keep surviving spinners moving around during the end screen.
        alive = [s for s in self.all_spinners if s.health > 0]
        for s in alive:
            s.move(self.playfield)
            for o in self.corner_obstacles:
                o.collide_with_spinner(s)
            s.draw(self.win, self.renderer.fonts)

        self._draw_health_bars()

        # --------------------------------------------------
        # Winner text should show the FULL team roster
        # (excluding *additional* spawned clones), even if some are dead.
        # --------------------------------------------------
        alive_team_a = [s for s in alive if s.team == "TeamA"]
        alive_team_b = [s for s in alive if s.team == "TeamB"]

        winner_team: Optional[str]
        if not alive_team_a and not alive_team_b:
            winner_team = None
        elif not alive_team_b:
            winner_team = "TeamA"
        elif not alive_team_a:
            winner_team = "TeamB"
        else:
            # Shouldn't happen in GAME_OVER, but keep it safe.
            winner_team = "TeamA" if len(alive_team_a) >= len(alive_team_b) else "TeamB"

        if winner_team is None:
            winner_text = "Draw!"
        else:
            full_roster = [
                s for s in self.all_spinners
                if s.team == winner_team and "Clone" not in s.name
            ]
            winner_text = f"{self._format_team_names([s.name for s in full_roster])} Win!"

        # Big centred banner that shrinks to fit.
        play_center_y = self.playfield.top + self.playfield.height // 2
        font_size = 80
        winner_font = pygame.font.SysFont("Helvetica", font_size)
        text_w, _ = winner_font.size(winner_text)
        while text_w > self.config.WIDTH * 0.9 and font_size > 12:
            font_size -= 1
            winner_font = pygame.font.SysFont("Helvetica", font_size)
            text_w, _ = winner_font.size(winner_text)

        surf = winner_font.render(winner_text, True, Colours.WHITE)
        rect = surf.get_rect(center=(self.config.WIDTH // 2, play_center_y))
        self.win.blit(surf, rect)

        # --------------------------------------------------
        # Damage stats (on-screen) - CLONE + ORIGINAL COMBINED
        # --------------------------------------------------
        header_font = pygame.font.SysFont("Helvetica", 28)
        stats_font = pygame.font.SysFont("Helvetica", 22)

        header_surface = header_font.render("Damage Stats", True, Colours.WHITE)
        header_rect = header_surface.get_rect(center=(self.config.WIDTH // 2, play_center_y + 110))
        self.win.blit(header_surface, header_rect)

        aggregated = self._aggregate_clone_stats()

        line_y = header_rect.bottom + 10
        line_spacing = 24
        for entry in aggregated:
            team_colour = Colours.BLUE if entry["team"] == "TeamA" else Colours.RED

            line = (
                f"{entry['name']} ({entry['team']}) - "
                f"Damage: {entry['damage']}, Health: {entry['health']}"
            )
            line_surface = stats_font.render(line, True, team_colour)

            line_rect = line_surface.get_rect(
                center=(self.config.WIDTH // 2, line_y)
            )
            self.win.blit(line_surface, line_rect)

            line_y += line_spacing

    def _format_team_names(self, names: List[str]) -> str:
        """Human-friendly list formatting: A, B and C."""
        names = [n for n in names if n]
        if not names:
            return "Team"
        if len(names) == 1:
            return names[0]
        if len(names) == 2:
            return f"{names[0]} and {names[1]}"
        return ", ".join(names[:-1]) + f" and {names[-1]}"

    # --------------------------------------------------
    # UI HELPERS
    # --------------------------------------------------

    def _get_role_indicator(self, spinner: Spinner):
        """
        Build a list of (text, colour) segments to be rendered in the UI.

        This allows multi-colour "tags" such as:
        - role tag: [V], [C], [G:x], [N]
        - item tags: [S], [D]
        """
        segments = []

        # Role tags.
        if spinner.role == SpecialRole.VENOM:
            segments.append(("[V]", Colours.GREEN))
        elif spinner.role == SpecialRole.CLONE:
            segments.append(("[C]", Colours.BLUE))
        elif spinner.role == SpecialRole.GLITCH:
            segments.append((f"[G:{spinner.glitch_charges}]", Colours.PURPLE))
        elif spinner.role == SpecialRole.NONE:
            segments.append(("[N]", Colours.WHITE))

        # Item tags (independent colours).
        if spinner.shield:
            segments.append(("[S]", Colours.CYAN))
        if spinner.carrying_dagger:
            segments.append(("[D]", Colours.DARK_RED))

        return segments if segments else None

    def _draw_health_bars(self):
        """Draw both teams' health bars in the top UI strip."""
        start_y = 35
        spacing = 40

        team_a = [s for s in self.all_spinners if s.team == "TeamA"]
        team_b = [s for s in self.all_spinners if s.team == "TeamB"]

        # Team A on the left.
        for i, s in enumerate(team_a):
            self.renderer.draw_health_bar(
                self.win,
                30,
                start_y + i * spacing,
                s.health,
                s.name,
                team_colour=Colours.BLUE,
                max_health=130 if s.role == SpecialRole.TITAN else 100,
                role_indicator=self._get_role_indicator(s)
            )

        # Team B on the right.
        for i, s in enumerate(team_b):
            self.renderer.draw_health_bar(
                self.win,
                self.config.WIDTH - 30,
                start_y + i * spacing,
                s.health,
                s.name,
                align="right",
                team_colour=Colours.RED,
                max_health=130 if s.role == SpecialRole.TITAN else 100,
                role_indicator=self._get_role_indicator(s)
            )

    # --------------------------------------------------
    # DELAYED VICTORY (POISON RESOLUTION)
    # --------------------------------------------------

    def _check_for_delayed_victory(self) -> bool:
        """
        If a match ends while poison effects are still ticking, we delay the
        winner announcement until poison fully resolves.
        """
        alive = [s for s in self.all_spinners if s.health > 0]
        return any(s.poison_ticks > 0 for s in alive)

    def _update_delayed_victory_state(self):
        """
        Continue updating status effects (e.g., poison) until they have finished.
        Once no poison remains, transition to GAME_OVER.
        """
        for s in self.all_spinners:
            s._update_status_effects()

        if not any(s.poison_ticks > 0 for s in self.all_spinners):
            self.game_state = GameState.GAME_OVER
            self.match_end_time = pygame.time.get_ticks()

    def _render_delayed_victory(self):
        """
        Draw the match as normal but show a small message indicating we are waiting
        for poison effects to finish resolving.
        """
        for o in self.corner_obstacles:
            o.draw(self.win)

        self.renderer.draw_game_title(self.win)

        for s in self.all_spinners:
            if s.health > 0:
                s.draw(self.win, self.renderer.fonts)

        self._draw_health_bars()

        font = pygame.font.SysFont("Helvetica", 40)
        surf = font.render("Waiting for poison effects...", True, Colours.YELLOW)
        rect = surf.get_rect(center=self.playfield.center)
        self.win.blit(surf, rect)


def main():
    """Entry point for running the game."""
    Game().run()


if __name__ == "__main__":
    main()