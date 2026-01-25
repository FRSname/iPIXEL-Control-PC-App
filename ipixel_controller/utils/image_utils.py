"""
Image processing utilities.

Provides functions for thumbnail generation, image resizing, and other
image manipulation tasks.
"""

import os
import base64
from io import BytesIO
from typing import Tuple, Optional, Union
from PIL import Image


# Default display dimensions
DEFAULT_WIDTH = 64
DEFAULT_HEIGHT = 16


def generate_thumbnail(
    image_path: str,
    max_size: Tuple[int, int] = (64, 16)
) -> Optional[Image.Image]:
    """
    Generate a thumbnail from an image file.

    Args:
        image_path: Path to the source image
        max_size: Maximum dimensions (width, height) for the thumbnail

    Returns:
        PIL Image object or None if image couldn't be loaded
    """
    try:
        with Image.open(image_path) as img:
            # Handle animated GIFs - use first frame
            if hasattr(img, 'n_frames') and img.n_frames > 1:
                img.seek(0)

            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Create thumbnail (maintains aspect ratio)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            return img.copy()

    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None


def image_to_base64(
    img: Image.Image,
    format: str = 'PNG'
) -> str:
    """
    Convert a PIL Image to base64 string.

    Args:
        img: PIL Image object
        format: Output format (PNG, JPEG, etc.)

    Returns:
        Base64 encoded string
    """
    buffer = BytesIO()
    img.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def base64_to_image(b64_string: str) -> Optional[Image.Image]:
    """
    Convert a base64 string to PIL Image.

    Args:
        b64_string: Base64 encoded image data

    Returns:
        PIL Image object or None on error
    """
    try:
        image_data = base64.b64decode(b64_string)
        return Image.open(BytesIO(image_data))
    except Exception:
        return None


def resize_to_display(
    img: Image.Image,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    method: str = 'fit'
) -> Image.Image:
    """
    Resize an image to fit the display dimensions.

    Args:
        img: Source PIL Image
        width: Target width
        height: Target height
        method: Resize method:
            - 'fit': Scale to fit within bounds (may have letterboxing)
            - 'fill': Scale to fill bounds (may crop)
            - 'stretch': Stretch to exact dimensions
            - 'crop': Crop from center to exact dimensions

    Returns:
        Resized PIL Image
    """
    if method == 'stretch':
        return img.resize((width, height), Image.Resampling.LANCZOS)

    elif method == 'fill':
        # Scale to fill, then center crop
        ratio = max(width / img.width, height / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        # Center crop
        left = (img.width - width) // 2
        top = (img.height - height) // 2
        return img.crop((left, top, left + width, top + height))

    elif method == 'crop':
        # Direct center crop without scaling
        left = (img.width - width) // 2
        top = (img.height - height) // 2
        if left < 0 or top < 0:
            # Image smaller than target, use fit instead
            method = 'fit'
        else:
            return img.crop((left, top, left + width, top + height))

    # Default: 'fit' - scale to fit within bounds
    ratio = min(width / img.width, height / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    img = img.resize(new_size, Image.Resampling.LANCZOS)

    # Center on canvas
    canvas = Image.new('RGB', (width, height), (0, 0, 0))
    offset = ((width - img.width) // 2, (height - img.height) // 2)
    canvas.paste(img, offset)
    return canvas


def create_solid_color_image(
    color: Union[str, Tuple[int, int, int]],
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT
) -> Image.Image:
    """
    Create a solid color image.

    Args:
        color: Color as hex string "#RRGGBB" or RGB tuple
        width: Image width
        height: Image height

    Returns:
        PIL Image with solid color
    """
    if isinstance(color, str):
        from .formatters import hex_to_rgb
        color = hex_to_rgb(color)

    return Image.new('RGB', (width, height), color)


def save_temp_image(
    img: Image.Image,
    filename: str = 'ipixel_temp.png'
) -> str:
    """
    Save an image to a temporary file.

    Args:
        img: PIL Image to save
        filename: Filename to use in temp directory

    Returns:
        Full path to the saved file
    """
    from .paths import get_temp_path
    path = get_temp_path(filename)
    img.save(path, 'PNG')
    return path


def load_image_safe(path: str) -> Optional[Image.Image]:
    """
    Safely load an image, handling errors gracefully.

    Args:
        path: Path to the image file

    Returns:
        PIL Image or None on error
    """
    try:
        if not os.path.isfile(path):
            return None
        return Image.open(path)
    except Exception:
        return None


def get_gif_frames(path: str) -> list:
    """
    Extract all frames from an animated GIF.

    Args:
        path: Path to the GIF file

    Returns:
        List of PIL Image frames
    """
    frames = []
    try:
        with Image.open(path) as img:
            for i in range(getattr(img, 'n_frames', 1)):
                img.seek(i)
                frames.append(img.copy())
    except Exception:
        pass
    return frames
