import pygame
from typing import List, Tuple

from constants import Colours
from spinner import Spinner


class CornerObstacle:
    """
    Corner obstacle made from two triangular ramps, positioned fully inside the playfield.

    Each corner is built from two triangles:
      - a short “lip” section (30px)
      - a longer ramp section (self.radius)

    The collision is handled by treating each triangle edge as a line segment and resolving:
      1) penetration (push the spinner out)
      2) velocity (reflect/bounce if the spinner is moving into the edge)
    """

    def __init__(self, corner: str, bounds: pygame.Rect):
        self.corner = corner
        self.colour = Colours.WHITE  # British spelling
        self.radius = 100           # How far the ramp extends from the corner
        self.triangles = self._create_triangles(bounds)

    def _create_triangles(self, b: pygame.Rect) -> List[List[Tuple[int, int]]]:
        """
        Create two triangles for the chosen corner.

        Points are ordered, but collision treats every edge anyway, so winding isn’t critical.
        """
        lip = 30  # Thickness of the short “lip” part of the corner wedge

        if self.corner == "topleft":
            return [
                [(b.left, b.top), (b.left + lip, b.top), (b.left, b.top + self.radius)],
                [(b.left, b.top), (b.left + self.radius, b.top), (b.left, b.top + lip)],
            ]

        if self.corner == "topright":
            return [
                [(b.right, b.top), (b.right - lip, b.top), (b.right, b.top + self.radius)],
                [(b.right, b.top), (b.right - self.radius, b.top), (b.right, b.top + lip)],
            ]

        if self.corner == "bottomleft":
            return [
                [(b.left, b.bottom), (b.left + lip, b.bottom), (b.left, b.bottom - self.radius)],
                [(b.left, b.bottom), (b.left + self.radius, b.bottom), (b.left, b.bottom - lip)],
            ]

        if self.corner == "bottomright":
            return [
                [(b.right, b.bottom), (b.right - lip, b.bottom), (b.right, b.bottom - self.radius)],
                [(b.right, b.bottom), (b.right - self.radius, b.bottom), (b.right, b.bottom - lip)],
            ]

        return []

    def draw(self, win: pygame.Surface) -> None:
        """Draw both ramp triangles."""
        for tri in self.triangles:
            pygame.draw.polygon(win, self.colour, tri)

    def collide_with_spinner(self, spinner: Spinner) -> None:
        """
        Handle spinner collision against all triangle edges.

        Notes:
        - We do multiple passes because the spinner can overlap more than one edge at once
          (common in corners). Each pass resolves a bit more penetration until stable.
        - We treat each triangle edge as a finite line segment and find the closest point on
          the segment to the spinner centre.
        """
        passes = 4

        for _ in range(passes):
            any_collision = False

            for tri in self.triangles:
                # Each triangle has 3 edges: (0->1), (1->2), (2->0)
                edges = [(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])]

                for p1, p2 in edges:
                    start = pygame.Vector2(p1)
                    end = pygame.Vector2(p2)

                    edge_vec = end - start
                    edge_len = edge_vec.length()
                    if edge_len == 0:
                        continue

                    edge_dir = edge_vec / edge_len
                    spinner_pos = pygame.Vector2(spinner.x, spinner.y)

                    # Project spinner centre onto the edge (clamped to the segment)
                    to_spinner = spinner_pos - start
                    projection = max(0.0, min(edge_len, to_spinner.dot(edge_dir)))
                    closest_point = start + edge_dir * projection

                    # Vector from the closest point on the edge to the spinner centre
                    separation = spinner_pos - closest_point
                    distance = separation.length()

                    if distance < spinner.radius:
                        # ---- 1) Resolve penetration (push out) ----
                        #
                        # Use the separation direction to push the spinner out of the edge.
                        # If perfectly centred on the closest point (distance == 0),
                        # fall back to a perpendicular direction.
                        if distance == 0:
                            # Perpendicular to the edge (one of the normals)
                            push_dir = pygame.Vector2(-edge_dir.y, edge_dir.x)
                        else:
                            push_dir = separation / distance

                        # Push slightly beyond the boundary to reduce “sticking”
                        push_amount = (spinner.radius - distance) + 1.5
                        spinner.x += push_dir.x * push_amount
                        spinner.y += push_dir.y * push_amount

                        # ---- 2) Resolve velocity (bounce) ----
                        #
                        # Only reflect if moving into the surface (dot < 0).
                        velocity = pygame.Vector2(spinner.vx, spinner.vy)
                        if velocity.dot(push_dir) < 0:
                            reflected = velocity.reflect(push_dir)
                            spinner.vx, spinner.vy = reflected.x, reflected.y

                            # Anti-jitter: if the spinner is barely moving after collision,
                            # give it a definite nudge away so it escapes cleanly.
                            min_escape_speed = 0.5
                            if velocity.length() < min_escape_speed:
                                spinner.vx = push_dir.x * spinner.speed
                                spinner.vy = push_dir.y * spinner.speed

                        any_collision = True

            # If we made a full pass with no collisions, we’re stable.
            if not any_collision:
                break