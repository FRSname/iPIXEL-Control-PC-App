"""
Animation generator service.

Provides procedural generation of pixel art animations for LED display.
Includes Conway's Game of Life, Matrix rain, Fire effect, Starfield, and Plasma.
"""

import math
import random
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from PIL import Image

# Display dimensions
DEFAULT_WIDTH = 64
DEFAULT_HEIGHT = 16


@dataclass
class AnimationState:
    """Holds state for animations that need persistence between frames."""
    # Game of Life
    gol_grid: Optional[List[List[int]]] = None

    # Matrix Rain
    matrix_columns: Optional[List[int]] = None
    matrix_trails: Optional[List[List[int]]] = None

    # Fire Effect
    fire_buffer: Optional[List[List[int]]] = None

    # Starfield
    stars: Optional[List[Tuple[float, float, float]]] = None

    # General
    frame_count: int = 0


class AnimationType:
    """Animation type constants."""
    GAME_OF_LIFE = "game_of_life"
    MATRIX_RAIN = "matrix"
    FIRE = "fire"
    STARFIELD = "starfield"
    PLASMA = "plasma"


class ColorScheme:
    """Color scheme constants."""
    WHITE = "white"
    GREEN = "green"
    BLUE = "blue"
    RED = "red"
    RAINBOW = "rainbow"


class AnimationGenerator:
    """
    Generates procedural pixel art animations.

    Each animation type has its own generation method that produces
    frames suitable for LED display.

    Usage:
        generator = AnimationGenerator(64, 16)
        state = AnimationState()

        # Generate frames in a loop
        for frame_num in range(100):
            image = generator.generate_frame(
                AnimationType.GAME_OF_LIFE,
                frame_num,
                ColorScheme.GREEN,
                state
            )
            # Send image to display
    """

    def __init__(self, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
        """
        Initialize the animation generator.

        Args:
            width: Display width in pixels
            height: Display height in pixels
        """
        self.width = width
        self.height = height

    def generate_frame(
        self,
        animation_type: str,
        frame_num: int,
        color_scheme: str,
        state: AnimationState,
        **options
    ) -> Image.Image:
        """
        Generate a single animation frame.

        Args:
            animation_type: Type of animation (see AnimationType)
            frame_num: Current frame number
            color_scheme: Color scheme to use (see ColorScheme)
            state: AnimationState for persistence
            **options: Animation-specific options

        Returns:
            PIL Image of the frame
        """
        state.frame_count = frame_num

        if animation_type == AnimationType.GAME_OF_LIFE:
            return self._generate_game_of_life(frame_num, color_scheme, state, **options)
        elif animation_type == AnimationType.MATRIX_RAIN:
            return self._generate_matrix(frame_num, color_scheme, state, **options)
        elif animation_type == AnimationType.FIRE:
            return self._generate_fire(frame_num, color_scheme, state, **options)
        elif animation_type == AnimationType.STARFIELD:
            return self._generate_starfield(frame_num, color_scheme, state, **options)
        elif animation_type == AnimationType.PLASMA:
            return self._generate_plasma(frame_num, color_scheme, state, **options)
        else:
            # Default to blank frame
            return Image.new('RGB', (self.width, self.height), (0, 0, 0))

    def _generate_game_of_life(
        self,
        frame_num: int,
        color_scheme: str,
        state: AnimationState,
        density: float = 0.3,
        **options
    ) -> Image.Image:
        """
        Generate Conway's Game of Life frame.

        Args:
            density: Initial cell density (0.0 to 1.0)
        """
        # Initialize grid on first frame
        if state.gol_grid is None or frame_num == 0:
            state.gol_grid = [
                [1 if random.random() < density else 0 for _ in range(self.width)]
                for _ in range(self.height)
            ]

        # Create image from current state
        img = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        pixels = img.load()

        for y in range(self.height):
            for x in range(self.width):
                if state.gol_grid[y][x]:
                    color = self._get_color(color_scheme, frame_num, x, y, 1.0)
                    pixels[x, y] = color

        # Calculate next generation
        new_grid = [[0] * self.width for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                neighbors = self._count_neighbors(state.gol_grid, x, y)
                if state.gol_grid[y][x]:
                    # Living cell
                    new_grid[y][x] = 1 if neighbors in (2, 3) else 0
                else:
                    # Dead cell
                    new_grid[y][x] = 1 if neighbors == 3 else 0

        state.gol_grid = new_grid
        return img

    def _count_neighbors(self, grid: List[List[int]], x: int, y: int) -> int:
        """Count living neighbors for a cell."""
        count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                ny = (y + dy) % self.height
                nx = (x + dx) % self.width
                count += grid[ny][nx]
        return count

    def _generate_matrix(
        self,
        frame_num: int,
        color_scheme: str,
        state: AnimationState,
        **options
    ) -> Image.Image:
        """Generate Matrix rain effect frame."""
        # Initialize on first frame
        if state.matrix_columns is None or frame_num == 0:
            state.matrix_columns = [random.randint(-self.height, 0) for _ in range(self.width)]
            state.matrix_trails = [[0] * self.height for _ in range(self.width)]

        img = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        pixels = img.load()

        for x in range(self.width):
            # Move column down
            state.matrix_columns[x] += 1
            if state.matrix_columns[x] >= self.height + 8:
                state.matrix_columns[x] = -random.randint(0, self.height)

            y = state.matrix_columns[x]

            # Draw trail with fade
            for trail_offset in range(8):
                ty = y - trail_offset
                if 0 <= ty < self.height:
                    brightness = 1.0 - (trail_offset / 8.0)
                    color = self._get_color(color_scheme, frame_num, x, ty, brightness)
                    pixels[x, ty] = color

        return img

    def _generate_fire(
        self,
        frame_num: int,
        color_scheme: str,
        state: AnimationState,
        **options
    ) -> Image.Image:
        """Generate fire effect frame."""
        # Initialize buffer
        if state.fire_buffer is None or frame_num == 0:
            state.fire_buffer = [[0] * self.width for _ in range(self.height + 2)]

        # Set bottom row to random heat values
        for x in range(self.width):
            state.fire_buffer[self.height + 1][x] = random.randint(200, 255)
            state.fire_buffer[self.height][x] = random.randint(150, 255)

        # Propagate fire upward
        for y in range(self.height):
            for x in range(self.width):
                # Average of pixels below with decay
                total = 0
                for dx in (-1, 0, 1):
                    nx = (x + dx) % self.width
                    total += state.fire_buffer[y + 1][nx]
                    total += state.fire_buffer[y + 2][nx]
                avg = total // 6
                state.fire_buffer[y][x] = max(0, avg - random.randint(0, 10))

        # Create image
        img = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        pixels = img.load()

        for y in range(self.height):
            for x in range(self.width):
                heat = state.fire_buffer[y][x]
                if heat > 0:
                    # Fire color gradient: black -> red -> orange -> yellow -> white
                    if heat < 85:
                        pixels[x, y] = (heat * 3, 0, 0)
                    elif heat < 170:
                        pixels[x, y] = (255, (heat - 85) * 3, 0)
                    else:
                        pixels[x, y] = (255, 255, (heat - 170) * 3)

        return img

    def _generate_starfield(
        self,
        frame_num: int,
        color_scheme: str,
        state: AnimationState,
        num_stars: int = 30,
        **options
    ) -> Image.Image:
        """Generate parallax starfield frame."""
        # Initialize stars: (x, y, speed)
        if state.stars is None or frame_num == 0:
            state.stars = []
            for _ in range(num_stars):
                x = random.uniform(0, self.width)
                y = random.uniform(0, self.height)
                speed = random.choice([0.5, 1.0, 2.0])  # 3 depth levels
                state.stars.append((x, y, speed))

        img = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        pixels = img.load()

        # Move and draw stars
        new_stars = []
        for x, y, speed in state.stars:
            # Move star
            x -= speed
            if x < 0:
                x = self.width
                y = random.uniform(0, self.height)

            new_stars.append((x, y, speed))

            # Draw star with brightness based on speed
            ix, iy = int(x), int(y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                brightness = speed / 2.0  # Faster = brighter (closer)
                color = self._get_color(color_scheme, frame_num, ix, iy, brightness)
                pixels[ix, iy] = color

        state.stars = new_stars
        return img

    def _generate_plasma(
        self,
        frame_num: int,
        color_scheme: str,
        state: AnimationState,
        **options
    ) -> Image.Image:
        """Generate plasma wave effect frame."""
        img = Image.new('RGB', (self.width, self.height), (0, 0, 0))
        pixels = img.load()

        t = frame_num * 0.1  # Time factor

        for y in range(self.height):
            for x in range(self.width):
                # Combine multiple sine waves
                v1 = math.sin(x / 8.0 + t)
                v2 = math.sin(y / 6.0 + t * 0.5)
                v3 = math.sin((x + y) / 10.0 + t * 0.3)
                v4 = math.sin(math.sqrt(x*x + y*y) / 8.0 + t * 0.7)

                value = (v1 + v2 + v3 + v4) / 4.0  # -1 to 1
                brightness = (value + 1.0) / 2.0  # 0 to 1

                color = self._get_color(color_scheme, frame_num, x, y, brightness)
                pixels[x, y] = color

        return img

    def _get_color(
        self,
        scheme: str,
        frame_num: int,
        x: int,
        y: int,
        brightness: float
    ) -> Tuple[int, int, int]:
        """
        Get RGB color for given scheme and brightness.

        Args:
            scheme: Color scheme name
            frame_num: Current frame number
            x, y: Pixel position
            brightness: Brightness level (0.0 to 1.0)

        Returns:
            RGB tuple
        """
        brightness = max(0.0, min(1.0, brightness))
        b = int(brightness * 255)

        if scheme == ColorScheme.WHITE:
            return (b, b, b)
        elif scheme == ColorScheme.GREEN:
            return (0, b, 0)
        elif scheme == ColorScheme.BLUE:
            return (0, 0, b)
        elif scheme == ColorScheme.RED:
            return (b, 0, 0)
        elif scheme == ColorScheme.RAINBOW:
            # Rainbow cycle based on position and time
            hue = (x + y + frame_num * 2) % 360
            return self._hsv_to_rgb(hue, 1.0, brightness)
        else:
            return (b, b, b)

    def _hsv_to_rgb(
        self,
        h: float,
        s: float,
        v: float
    ) -> Tuple[int, int, int]:
        """Convert HSV to RGB."""
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c

        if h < 60:
            r, g, b = c, x, 0
        elif h < 120:
            r, g, b = x, c, 0
        elif h < 180:
            r, g, b = 0, c, x
        elif h < 240:
            r, g, b = 0, x, c
        elif h < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x

        return (
            int((r + m) * 255),
            int((g + m) * 255),
            int((b + m) * 255)
        )
