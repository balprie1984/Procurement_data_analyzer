"""Shared logo formatting and header rendering for Procurement Data Analyzer."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps, ImageStat


def _sample_background(image: Image.Image) -> tuple[int, int, int]:
    """Choose a canvas color that blends with opaque logos at their edges."""
    rgb_image = image.convert("RGB")
    patch_width = max(1, round(rgb_image.width * 0.04))
    patch_height = max(1, round(rgb_image.height * 0.04))
    corners = (
        (0, 0, patch_width, patch_height),
        (rgb_image.width - patch_width, 0, rgb_image.width, patch_height),
        (0, rgb_image.height - patch_height, patch_width, rgb_image.height),
        (rgb_image.width - patch_width, rgb_image.height - patch_height, rgb_image.width, rgb_image.height),
    )
    samples = [ImageStat.Stat(rgb_image.crop(box)).mean for box in corners]
    return tuple(round(sum(sample[channel] for sample in samples) / len(samples)) for channel in range(3))


def format_logo_for_display(
    source: Path,
    output: Path,
    *,
    crop_box: tuple[int, int, int, int] | None = None,
    canvas_size: tuple[int, int] = (1000, 700),
    padding: float = 0.10,
) -> Path:
    """Prepare a contained, padded logo image so its edges never get clipped.

    ``crop_box`` is optional and should only be used for known source images with
    large margins. User-uploaded logos are kept whole and fit inside the canvas.
    """
    if not 0 <= padding < 0.45:
        raise ValueError("padding must be between 0 and 0.45")
    if output.exists() and output.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return output

    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        if crop_box is not None:
            left, top, right, bottom = crop_box
            if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
                raise ValueError(f"Crop box {crop_box} is outside logo dimensions {image.size}.")
            image = image.crop(crop_box)

        has_alpha = image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)
        image = image.convert("RGBA" if has_alpha else "RGB")
        inner_size = (
            max(1, round(canvas_size[0] * (1 - 2 * padding))),
            max(1, round(canvas_size[1] * (1 - 2 * padding))),
        )
        image = ImageOps.contain(image, inner_size, method=Image.Resampling.LANCZOS)

        canvas_mode = "RGBA" if has_alpha else "RGB"
        background = (255, 255, 255, 0) if has_alpha else _sample_background(image)
        canvas = Image.new(canvas_mode, canvas_size, background)
        offset = ((canvas.width - image.width) // 2, (canvas.height - image.height) // 2)
        if has_alpha:
            canvas.alpha_composite(image, dest=offset)
        else:
            canvas.paste(image, offset)

        output.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output, format="PNG", optimize=True)
    return output


def display_branding(
    logo_source: Path,
    *,
    title: str,
    subtitle: str = "",
    crop_box: tuple[int, int, int, int] | None = None,
    logo_width: int = 220,
) -> Path:
    """Format a logo and render it left of a vertically centered app title."""
    import streamlit as st

    formatted_logo = logo_source.with_name(f"{logo_source.stem}-formatted-v3.png")
    formatted_logo = format_logo_for_display(logo_source, formatted_logo, crop_box=crop_box)

    logo_column, title_column = st.columns([1.7, 5])
    with logo_column:
        st.image(formatted_logo, width=logo_width)
    with title_column:
        subtitle_markup = f'<div class="brand-caption">{subtitle}</div>' if subtitle else ""
        st.markdown(
            f'<div class="brand-copy"><div class="brand-title">{title}</div>{subtitle_markup}</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="brand-divider"></div>', unsafe_allow_html=True)
    return formatted_logo
