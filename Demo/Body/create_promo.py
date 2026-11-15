from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parent
INTRO = ROOT / "gui-1.mp4"
DASHBOARD = ROOT / "gui-2.mp4"
LOGO = ROOT.parent.parent / "Project" / "logo.png"
OUTPUT = ROOT / "AstraHealth-platform-demo.mp4"

WIDTH, HEIGHT, FPS = 1280, 720, 24
INTRO_SECONDS = 2.2
MAIN_SECONDS = 13.2
OUTRO_SECONDS = 1.4

FONT_DISPLAY = r"C:\Windows\Fonts\bahnschrift.ttf"
FONT_BODY = r"C:\Windows\Fonts\arial.ttf"
FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"

SCENES = [
    (0.0, 2.8, "LIVE HEALTH & HABITABILITY", "3-second simulated readings · trends · risk alerts"),
    (2.8, 5.0, "AI-READY HEALTH INSIGHTS", "Rule alerts · Isolation Forest anomalies · LSTM forecast status"),
    (5.0, 7.1, "OPT-IN CONVERSATIONAL AI", "Locally hosted assistant · stateless by design"),
    (7.1, 9.25, "PERSONALIZED NEXT STEPS", "Mood + sleep check-ins · recommendations from shared context"),
    (9.25, 11.6, "MISSION CONTROL", "Queue updates and help requests for simulated contact windows"),
    (11.6, MAIN_SECONDS, "MODULAR SERVICES", "React + TypeScript · FastAPI · SQLite · Docker Compose"),
]


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 3


def fit_frame(frame: np.ndarray, width: int, height: int, background: tuple[int, int, int], fill: bool = False) -> np.ndarray:
    h, w = frame.shape[:2]
    scale = max(width / w, height / h) if fill else min(width / w, height / h)
    nw, nh = round(w * scale), round(h * scale)
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    canvas = np.full((height, width, 3), background, dtype=np.uint8)
    x, y = (width - nw) // 2, (height - nh) // 2
    left, top = max(0, x), max(0, y)
    right, bottom = min(width, x + nw), min(height, y + nh)
    canvas[top:bottom, left:right] = resized[top - y:bottom - y, left - x:right - x]
    return canvas


def intro_frame(frame: np.ndarray) -> np.ndarray:
    canvas = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    canvas[:] = (4, 7, 15)
    content = fit_frame(frame, 760, 620, (4, 7, 15), fill=False)
    x, y = (WIDTH - 760) // 2, 16
    canvas[y:y + 620, x:x + 760] = content
    return canvas


def dashboard_frame(frame: np.ndarray) -> np.ndarray:
    canvas = np.full((HEIGHT, WIDTH, 3), (244, 246, 250), dtype=np.uint8)
    content = fit_frame(frame, WIDTH, 590, (244, 246, 250), fill=False)
    y = 14
    canvas[y:y + 590] = content
    return canvas


def make_logo_mark(size: int) -> Image.Image:
    logo = Image.open(LOGO).convert("RGBA")
    mark = logo.crop((180, 78, 1082, 980))
    return mark.resize((size, size), Image.Resampling.LANCZOS)


LOGO_MARK = make_logo_mark(48)
FONT_EYEBROW = load_font(FONT_BOLD, 11)
FONT_TITLE = load_font(FONT_DISPLAY, 27)
FONT_SUBTITLE = load_font(FONT_BODY, 15)
FONT_END_TITLE = load_font(FONT_DISPLAY, 36)
FONT_END_SUB = load_font(FONT_BODY, 15)


def draw_lower_third(frame: np.ndarray, eyebrow: str, title: str, subtitle: str, age: float, duration: float) -> np.ndarray:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    fade_in = ease(age / 0.28)
    fade_out = ease((duration - age) / 0.25) if age > duration - 0.25 else 1.0
    opacity = int(236 * min(fade_in, fade_out))
    slide = int(28 * (1 - fade_in))
    box = (28 + slide, 566, 1252 + slide, 696)
    draw.rounded_rectangle(box, radius=17, fill=(7, 14, 28, opacity), outline=(97, 119, 151, min(opacity, 155)), width=1)
    draw.rounded_rectangle((box[0], box[1] + 17, box[0] + 4, box[3] - 17), radius=2, fill=(198, 255, 0, opacity))
    badge_left = 47 + slide
    draw.ellipse((badge_left, 592, badge_left + 54, 646), fill=(14, 11, 156, opacity), outline=(198, 255, 0, opacity), width=2)
    draw.line([(badge_left + 12, 620), (badge_left + 18, 620), (badge_left + 23, 611), (badge_left + 29, 629), (badge_left + 35, 613), (badge_left + 40, 620), (badge_left + 44, 620)], fill=(198, 255, 0, opacity), width=2, joint="curve")

    logo_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    logo_layer.alpha_composite(LOGO_MARK, (50 + slide, 595))
    logo_layer.putalpha(logo_layer.getchannel("A"))
    image.alpha_composite(logo_layer)

    tx = 112 + slide
    white = (246, 249, 255, opacity)
    muted = (196, 207, 225, opacity)
    lime = (198, 255, 0, opacity)
    draw.text((tx, 578), eyebrow, font=FONT_EYEBROW, fill=lime)
    draw.text((tx, 595), title, font=FONT_TITLE, fill=white)
    draw.text((tx, 637), subtitle, font=FONT_SUBTITLE, fill=muted)

    # Restrained telemetry pulse and progress sweep tie the cards together.
    phase = (age * 1.3) % 1.0
    pulse = 3 + int(2 * (0.5 + 0.5 * math.sin(age * 5)))
    cx, cy = 1215 + slide, 586
    draw.ellipse((cx - pulse - 2, cy - pulse - 2, cx + pulse + 2, cy + pulse + 2), outline=(198, 255, 0, opacity // 3), width=1)
    draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=(198, 255, 0, opacity))
    bar_x1, bar_y, bar_x2 = 112 + slide, 684, 1218 + slide
    draw.rounded_rectangle((bar_x1, bar_y, bar_x2, bar_y + 2), radius=1, fill=(255, 255, 255, min(opacity, 45)))
    progress = 0.08 + 0.84 * phase
    draw.rounded_rectangle((bar_x1, bar_y, bar_x1 + int((bar_x2 - bar_x1) * progress), bar_y + 2), radius=1, fill=(198, 255, 0, opacity))

    image.alpha_composite(overlay)
    return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def draw_outro(frame: np.ndarray, t: float) -> np.ndarray:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGBA")
    tint = Image.new("RGBA", image.size, (4, 8, 18, 190))
    image.alpha_composite(tint)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    alpha = int(255 * ease(t / 0.32))

    mark = LOGO_MARK.resize((76, 76), Image.Resampling.LANCZOS)
    overlay.alpha_composite(mark, (WIDTH // 2 - 38, 210))
    draw.text((WIDTH // 2, 312), "ASTRAHEALTH", anchor="mm", font=FONT_END_TITLE, fill=(247, 249, 255, alpha))
    draw.rounded_rectangle((WIDTH // 2 - 130, 345, WIDTH // 2 + 130, 348), radius=2, fill=(198, 255, 0, alpha))
    draw.text((WIDTH // 2, 384), "Crew health, connected to Earth.", anchor="mm", font=FONT_END_SUB, fill=(213, 221, 235, alpha))
    draw.text((WIDTH // 2, 650), "SIMULATION PROTOTYPE  ·  NOT A CLINICAL ASSESSMENT", anchor="mm", font=FONT_EYEBROW, fill=(166, 180, 203, alpha))
    image.alpha_composite(overlay)
    return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def main() -> None:
    for path in (INTRO, DASHBOARD, LOGO):
        if not path.exists():
            raise FileNotFoundError(path)

    intro_cap = cv2.VideoCapture(str(INTRO))
    dash_cap = cv2.VideoCapture(str(DASHBOARD))
    intro_fps = intro_cap.get(cv2.CAP_PROP_FPS) or 30.0
    dash_fps = dash_cap.get(cv2.CAP_PROP_FPS) or 30.0
    intro_frames = round(INTRO_SECONDS * FPS)
    main_frames = round(MAIN_SECONDS * FPS)
    outro_frames = round(OUTRO_SECONDS * FPS)
    total_frames = intro_frames + main_frames + outro_frames

    dash_start = 1.2
    dash_cap.set(cv2.CAP_PROP_POS_FRAMES, round(dash_start * dash_fps))
    dash_next_index = round(dash_start * dash_fps) + 1
    ok, dash_current = dash_cap.read()
    if not ok:
        raise RuntimeError("Could not read the dashboard clip")

    writer = cv2.VideoWriter(str(OUTPUT), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("Could not create the MP4 writer")

    last_frame: np.ndarray | None = None
    outro_base: np.ndarray | None = None
    for index in range(intro_frames):
        target = index * intro_fps / FPS
        intro_cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, source = intro_cap.read()
        if not ok:
            break
        stage = intro_frame(source)
        age = index / FPS
        stage = draw_lower_third(stage, "ASTRAHEALTH  /  DEEP-SPACE CREW HEALTH", "HEALTH, IN MISSION CONTEXT", "One clear view of physical, wellbeing, and cabin conditions", age, INTRO_SECONDS)
        writer.write(stage)
        last_frame = stage

    for index in range(main_frames):
        target_index = round(dash_start * dash_fps + index * dash_fps / FPS)
        if target_index >= dash_next_index:
            for _ in range(target_index - dash_next_index + 1):
                ok, dash_current = dash_cap.read()
                if not ok:
                    break
            dash_next_index = target_index + 1
        if dash_current is None:
            raise RuntimeError("Dashboard clip ended before the edit was complete")
        stage = dashboard_frame(dash_current)
        outro_base = stage.copy()
        age = index / FPS
        scene = next(item for item in SCENES if item[0] <= age < item[1])
        stage = draw_lower_third(stage, "ASTRAHEALTH  /  MISSION HEALTH PLATFORM", scene[2], scene[3], age - scene[0], scene[1] - scene[0])
        writer.write(stage)
        last_frame = stage

    if last_frame is None:
        raise RuntimeError("No frames were rendered")
    outro_base = outro_base if outro_base is not None else last_frame
    for index in range(outro_frames):
        writer.write(draw_outro(outro_base, index / FPS))

    writer.release()
    intro_cap.release()
    dash_cap.release()
    print(f"Rendered {OUTPUT} · {total_frames} frames · {total_frames / FPS:.2f} sec · {WIDTH}x{HEIGHT} · {FPS} fps")


if __name__ == "__main__":
    main()
