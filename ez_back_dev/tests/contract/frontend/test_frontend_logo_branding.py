import struct
import zlib
from pathlib import Path


from repo_paths import canonical_document_path
from repo_paths import REPO_ROOT as PROJECT_ROOT
FRONTEND_ROOT = PROJECT_ROOT / "ez_front_dev"
BRAND_ASSET_ROOT = FRONTEND_ROOT / "src" / "shared" / "assets" / "brand"
LEGACY_IMAGE_ROOT = FRONTEND_ROOT / "src" / "assets" / "static" / "image"


def read(relative_path: str) -> str:
    if relative_path.replace("\\", "/").startswith("docs/"):
        return canonical_document_path(relative_path).read_text(encoding="utf-8")
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def rgba_png(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")

    offset = 8
    idat = bytearray()
    width = height = 0
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, colour_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", payload)
            )
            assert bit_depth == 8
            assert colour_type == 6
            assert compression == filtering == interlace == 0
        elif chunk_type == b"IDAT":
            idat.extend(payload)
        elif chunk_type == b"IEND":
            break

    raw = zlib.decompress(bytes(idat))
    stride = width * 4
    rows: list[bytearray] = []
    cursor = 0

    def paeth(left: int, above: int, upper_left: int) -> int:
        estimate = left + above - upper_left
        distances = (
            abs(estimate - left),
            abs(estimate - above),
            abs(estimate - upper_left),
        )
        return (left, above, upper_left)[distances.index(min(distances))]

    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        encoded = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        previous = rows[-1] if rows else bytearray(stride)
        decoded = bytearray(stride)
        for index, value in enumerate(encoded):
            left = decoded[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                decoded[index] = value
            elif filter_type == 1:
                decoded[index] = (value + left) & 0xFF
            elif filter_type == 2:
                decoded[index] = (value + above) & 0xFF
            elif filter_type == 3:
                decoded[index] = (value + ((left + above) // 2)) & 0xFF
            elif filter_type == 4:
                decoded[index] = (value + paeth(left, above, upper_left)) & 0xFF
            else:
                raise AssertionError(f"unsupported PNG filter {filter_type}")
        rows.append(decoded)

    return width, height, b"".join(rows)


def alpha_bounds(width: int, height: int, pixels: bytes) -> tuple[int, int, int, int]:
    coordinates = [
        (index % width, index // width)
        for index, alpha in enumerate(pixels[3::4])
        if alpha
    ]
    assert coordinates
    xs, ys = zip(*coordinates)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def test_selected_b05_logo_and_favicon_are_bounded_rgba_assets():
    logo = BRAND_ASSET_ROOT / "ezlogo-workbench-v2.png"
    favicon = FRONTEND_ROOT / "public" / "favicon.png"

    width, height, pixels = rgba_png(logo)
    assert (width, height) == (192, 192)
    left, top, right, bottom = alpha_bounds(width, height, pixels)
    assert max(right - left, bottom - top) <= 168
    assert abs((left + right) - width) <= 2
    assert abs((top + bottom) - height) <= 2
    assert logo.stat().st_size <= 96 * 1024

    favicon_width, favicon_height, favicon_pixels = rgba_png(favicon)
    assert (favicon_width, favicon_height) == (48, 48)
    assert alpha_bounds(favicon_width, favicon_height, favicon_pixels)


def test_production_uses_v2_logo_and_retains_rollback_assets():
    main_view = read("ez_front_dev/src/features/workspace/MainView.vue")
    onboarding = read(
        "ez_front_dev/src/features/onboarding/components/OnboardingShell.vue"
    )
    index = read("ez_front_dev/index.html")

    assert "ezlogo-workbench-v2.png" in main_view
    assert "ezlogo-workbench-v2.png" in onboarding
    assert 'width="38"' in main_view and 'height="38"' in main_view
    assert 'width="52"' in onboarding and 'height="52"' in onboarding
    assert 'rel="icon"' in index
    assert 'href="/favicon.png"' in index

    production_sources = [
        path
        for path in (FRONTEND_ROOT / "src").rglob("*")
        if path.suffix in {".vue", ".ts", ".css"}
    ]
    assert all(
        "ezlogo-workbench.png" not in path.read_text(encoding="utf-8")
        for path in production_sources
    )
    for legacy_name in ("ezlogo-workbench.png", "ezlogo.png", "logo.png"):
        assert (LEGACY_IMAGE_ROOT / legacy_name).is_file()


def test_logo_selection_is_recorded_in_iteration_log():
    log = read("docs/iteration-3-development-log.md")
    assert "B05" in log
    assert "ezlogo-workbench-v2.png" in log
    assert "favicon.png" in log
