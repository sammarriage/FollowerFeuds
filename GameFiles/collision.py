import math
import random
import pygame

from spinner import Spinner
from assets import AssetManager
from config import SpecialRole


class CollisionManager:
    """
    Centralised collision and combat-resolution logic for Spinner Battle.

    Responsibilities:
    - Detect overlap between two spinners
    - Apply special-case behaviour (e.g., Glitch phasing)
    - Resolve collision physics (elastic-ish impulse response)
    - Apply damage rules (dagger, shield, normal contact damage, venom on-hit)
    - Nudge the game along if too many spinners grind to a halt
    """

    @staticmethod
    def handle_spinner_collision(sp1: Spinner, sp2: Spinner, asset_manager: AssetManager):
        """
        Entry point for handling a potential collision between two spinners.
        This will early-exit if:
        - They are not overlapping
        - They are on the same team
        - A Glitch phasing event triggers (consumes the collision this frame)
        """
        dx = sp2.x - sp1.x
        dy = sp2.y - sp1.y
        distance = math.hypot(dx, dy)
        min_dist = sp1.radius + sp2.radius

        # No overlap → nothing to do.
        if distance >= min_dist:
            return

        # Same team → no damage and no special interaction.
        if sp1.team == sp2.team:
            return

        # -------------------------------------------------
        # Glitch phasing:
        # If a Glitch spinner is about to be hit by a dagger carrier and still has charges,
        # it begins "phasing through" the attacker instead of taking collision damage.
        # This intentionally consumes the collision event this frame.
        # -------------------------------------------------
        for glitch, attacker in [(sp1, sp2), (sp2, sp1)]:
            if CollisionManager._try_start_glitch_phase(glitch, attacker, asset_manager):
                return

        # -------------------------------------------------
        # Standard collision flow: resolve physics, then apply damage rules.
        # -------------------------------------------------
        CollisionManager._resolve_collision(sp1, sp2, dx, dy, distance, min_dist)
        CollisionManager._handle_damage(sp1, sp2, asset_manager)

    @staticmethod
    def _try_start_glitch_phase(glitch: Spinner, attacker: Spinner, asset_manager: AssetManager) -> bool:
        """
        If glitch is about to be hit by attacker's dagger and has charges, start phasing.
        Returns True if phasing started (collision consumed), False otherwise.
        """
        if (
            glitch.role != SpecialRole.GLITCH
            or not attacker.carrying_dagger
            or glitch.glitch_charges <= 0
            or glitch.shield
        ):
            return False
        if glitch.phasing_through != attacker:
            glitch.phasing_through = attacker
            glitch.phasing_start_time = pygame.time.get_ticks()
            asset_manager.play_sound("glitch")
        return True

    # -------------------------------------------------
    @staticmethod
    def _resolve_collision(sp1, sp2, dx, dy, distance, min_dist):
        """
        Resolve collision physics between two overlapping circles using a
        tangent/normal decomposition.

        Notes:
        - This treats the collision like an elastic response along the normal.
        - Tangential velocity components are preserved.
        - We also separate the spinners to remove overlap, otherwise they can "stick".
        """
        # Guard against divide-by-zero if two spinners end up exactly on top of each other.
        # (Rare, but can happen with high speeds or spawning.)
        if distance == 0:
            # Pick an arbitrary normal to separate them.
            nx, ny = 1.0, 0.0
        else:
            nx = dx / distance
            ny = dy / distance

        # Tangent is perpendicular to the normal.
        tx = -ny
        ty = nx

        # Project velocities onto tangent and normal axes.
        dpTan1 = sp1.vx * tx + sp1.vy * ty
        dpTan2 = sp2.vx * tx + sp2.vy * ty

        dpNorm1 = sp1.vx * nx + sp1.vy * ny
        dpNorm2 = sp2.vx * nx + sp2.vy * ny

        # 1D elastic collision along the normal axis.
        m1 = (dpNorm1 * (sp1.mass - sp2.mass) + 2 * sp2.mass * dpNorm2) / (sp1.mass + sp2.mass)
        m2 = (dpNorm2 * (sp2.mass - sp1.mass) + 2 * sp1.mass * dpNorm1) / (sp1.mass + sp2.mass)

        # Reconstruct final velocities from tangent + new normal components.
        sp1.vx = tx * dpTan1 + nx * m1
        sp1.vy = ty * dpTan1 + ny * m1
        sp2.vx = tx * dpTan2 + nx * m2
        sp2.vy = ty * dpTan2 + ny * m2

        # Push them apart so they are no longer overlapping.
        # The "+ 1" is a small bias to ensure separation even with rounding.
        overlap = 0.5 * (min_dist - distance + 1)
        sp1.x -= overlap * nx
        sp1.y -= overlap * ny
        sp2.x += overlap * nx
        sp2.y += overlap * ny

    # -------------------------------------------------
    @staticmethod
    def _apply_venom_on_hit(attacker: Spinner, target: Spinner, did_damage: bool):
        """Venom applies poison on a successful hit. Shields block poisoning."""
        if not did_damage:
            return
        if attacker.role == SpecialRole.VENOM and not target.shield and target.health > 0:
            print(f"VENOM HIT: {attacker.name} applying poison to {target.name}")
            target.apply_poison(attacker=attacker)

    @staticmethod
    def _try_dagger_hit(attacker: Spinner, target: Spinner, asset_manager: AssetManager) -> bool:
        """If attacker has dagger and target has no shield, deal dagger damage. Returns True if hit occurred."""
        if not attacker.carrying_dagger or target.shield:
            return False
        if attacker.role == SpecialRole.TITAN:
            dagger_damage = random.randint(20, 35)
            print(f"TITAN DAGGER: {attacker.name} dealing {dagger_damage} damage")
        else:
            dagger_damage = random.randint(15, 25)
        if attacker.role == SpecialRole.VENOM:
            dagger_damage = int(dagger_damage * 1.0)
            print(f"VENOM DAGGER: {attacker.name} dealing {dagger_damage} damage (1.0x multiplier)")

        actual_damage = min(dagger_damage, target.health)
        target.health = max(0, target.health - actual_damage)
        target.add_damage_text(actual_damage)
        attacker.damage_dealt += actual_damage
        attacker.carrying_dagger = False

        CollisionManager._apply_venom_on_hit(attacker, target, did_damage=(actual_damage > 0))
        asset_manager.play_sound("dagger_hit")
        return True

    @staticmethod
    def _try_shield_block(attacker: Spinner, target: Spinner, asset_manager: AssetManager) -> bool:
        """If attacker has dagger and target has shield, consume both. Returns True if block occurred."""
        if not attacker.carrying_dagger or not target.shield:
            return False
        attacker.carrying_dagger = False
        target.shield = False
        asset_manager.play_sound("shield_hit")
        return True

    @staticmethod
    def _apply_contact_damage(sp1: Spinner, sp2: Spinner, asset_manager: AssetManager):
        """Apply normal collision damage based on protection state (shield/dagger)."""
        damage_from_sp1_to_sp2 = random.randint(3, 5) if sp1.role == SpecialRole.TITAN else random.randint(1, 3)
        damage_from_sp2_to_sp1 = random.randint(3, 5) if sp2.role == SpecialRole.TITAN else random.randint(1, 3)

        sp1_has_protection = sp1.shield or sp1.carrying_dagger
        sp2_has_protection = sp2.shield or sp2.carrying_dagger

        if sp1_has_protection and not sp2_has_protection:
            actual_damage = min(damage_from_sp1_to_sp2, sp2.health)
            sp2.health = max(0, sp2.health - actual_damage)
            sp2.add_damage_text(actual_damage)
            sp1.damage_dealt += actual_damage
            CollisionManager._apply_venom_on_hit(sp1, sp2, did_damage=(actual_damage > 0))
            asset_manager.play_sound("regular_hit")
        elif sp2_has_protection and not sp1_has_protection:
            actual_damage = min(damage_from_sp2_to_sp1, sp1.health)
            sp1.health = max(0, sp1.health - actual_damage)
            sp1.add_damage_text(actual_damage)
            sp2.damage_dealt += actual_damage
            CollisionManager._apply_venom_on_hit(sp2, sp1, did_damage=(actual_damage > 0))
            asset_manager.play_sound("regular_hit")
        elif not sp1_has_protection and not sp2_has_protection:
            actual_damage_to_sp1 = min(damage_from_sp2_to_sp1, sp1.health)
            actual_damage_to_sp2 = min(damage_from_sp1_to_sp2, sp2.health)
            sp1.health = max(0, sp1.health - actual_damage_to_sp1)
            sp2.health = max(0, sp2.health - actual_damage_to_sp2)
            sp1.add_damage_text(actual_damage_to_sp1)
            sp2.add_damage_text(actual_damage_to_sp2)
            sp2.damage_dealt += actual_damage_to_sp1
            sp1.damage_dealt += actual_damage_to_sp2
            CollisionManager._apply_venom_on_hit(sp1, sp2, did_damage=(actual_damage_to_sp2 > 0))
            CollisionManager._apply_venom_on_hit(sp2, sp1, did_damage=(actual_damage_to_sp1 > 0))
            asset_manager.play_sound("regular_hit")

    @staticmethod
    def _handle_damage(sp1: Spinner, sp2: Spinner, asset_manager: AssetManager):
        """
        Apply combat rules after a collision has been confirmed and physics has been resolved.

        Damage priority:
        1) Dagger hits (high damage, consumes dagger)
        2) Shield vs dagger (both consumed, no health damage)
        3) Normal collision damage (small damage, depends on protection state)

        Venom behaviour:
        - Venom applies poison on any successful hit (dagger or collision),
          unless the target is shielded.
        """
        if sp1.health <= 0 or sp2.health <= 0:
            return

        for attacker, target in [(sp1, sp2), (sp2, sp1)]:
            if CollisionManager._try_dagger_hit(attacker, target, asset_manager):
                return

        for attacker, target in [(sp1, sp2), (sp2, sp1)]:
            if CollisionManager._try_shield_block(attacker, target, asset_manager):
                return

        CollisionManager._apply_contact_damage(sp1, sp2, asset_manager)

    # -------------------------------------------------
    @staticmethod
    def maintain_game_momentum(all_spinners):
        """
        If too many surviving spinners slow down below a threshold, give the slow ones
        a gentle kick so the match doesn't stall out.

        This is intentionally simple: it only boosts the spinners that are currently slow,
        and only triggers if more than half of living spinners are below the speed threshold.
        """
        active = [s for s in all_spinners if s.health > 0]
        if len(active) < 2:
            return

        slow = []
        for s in active:
            if math.hypot(s.vx, s.vy) < s.speed * 0.6:
                slow.append(s)

        if len(slow) > len(active) * 0.5:
            for s in slow:
                speed = math.hypot(s.vx, s.vy)
                if speed == 0:
                    # Completely stationary: pick a random direction.
                    angle = random.uniform(0, 2 * math.pi)
                    s.vx = 8 * math.cos(angle)
                    s.vy = 8 * math.sin(angle)
                else:
                    # Scale current velocity up to a fixed baseline speed.
                    factor = 8 / speed
                    s.vx *= factor
                    s.vy *= factor