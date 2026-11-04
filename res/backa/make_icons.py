# Gera os ícones compartilhados dos presets Backa (clima e alerta) em icons/*.png, 96x96 com transparência
# Desenha em alta resolução e reduz, para ficar com bordas suaves
# Uso: ..\..\.venv\Scripts\python.exe make_icons.py
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 96
S = 4  # fator de super-amostragem
N = SIZE * S
OUT = Path(__file__).parent / "icons"

SUN = (255, 196, 40)
MOON = (210, 220, 255)
CLOUD = (205, 212, 225)
CLOUD_DARK = (140, 148, 165)
RAIN = (80, 170, 255)
BOLT = (255, 220, 60)
YELLOW = (255, 196, 0)
RED = (255, 60, 60)


def canvas():
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def save(img, name):
    img.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / f"{name}.png")


def sun(d, cx, cy, r):
    import math
    for i in range(8):
        a = i * math.pi / 4
        x1, y1 = cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35
        x2, y2 = cx + math.cos(a) * r * 1.85, cy + math.sin(a) * r * 1.85
        d.line((x1, y1, x2, y2), fill=SUN, width=int(r * 0.28))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=SUN)


def moon(d, cx, cy, r):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=MOON)
    d.ellipse((cx - r * 0.35, cy - r * 1.15, cx + r * 1.65, cy + r * 0.85), fill=(0, 0, 0, 0))


def cloud(d, x, y, w, color):
    h = w * 0.55
    d.ellipse((x, y + h * 0.35, x + w * 0.5, y + h), fill=color)
    d.ellipse((x + w * 0.2, y, x + w * 0.75, y + h * 0.85), fill=color)
    d.ellipse((x + w * 0.5, y + h * 0.25, x + w, y + h), fill=color)
    d.rectangle((x + w * 0.25, y + h * 0.6, x + w * 0.8, y + h), fill=color)


def drops(d, x, y, n, length, color):
    for i in range(n):
        dx = x + i * N * 0.2
        d.line((dx, y, dx - N * 0.06, y + length), fill=color, width=int(N * 0.07))


def main():
    OUT.mkdir(exist_ok=True)

    img, d = canvas(); sun(d, N / 2, N / 2, N * 0.22); save(img, "clear_day")
    img, d = canvas(); moon(d, N / 2, N / 2, N * 0.36); save(img, "clear_night")

    img, d = canvas(); sun(d, N * 0.38, N * 0.36, N * 0.16); cloud(d, N * 0.18, N * 0.42, N * 0.78, CLOUD); save(img, "partly_day")
    img, d = canvas(); moon(d, N * 0.4, N * 0.36, N * 0.22); cloud(d, N * 0.18, N * 0.42, N * 0.78, CLOUD); save(img, "partly_night")

    img, d = canvas(); cloud(d, N * 0.04, N * 0.22, N * 0.92, CLOUD); save(img, "cloudy")

    img, d = canvas()
    for i, yy in enumerate((0.3, 0.5, 0.7)):
        d.rounded_rectangle((N * (0.12 + 0.06 * (i % 2)), N * yy, N * (0.88 - 0.06 * (i % 2)), N * yy + N * 0.09),
                            radius=N * 0.045, fill=CLOUD)
    save(img, "fog")

    img, d = canvas(); cloud(d, N * 0.06, N * 0.06, N * 0.88, CLOUD); drops(d, N * 0.32, N * 0.7, 3, N * 0.12, RAIN); save(img, "drizzle")
    img, d = canvas(); cloud(d, N * 0.06, N * 0.06, N * 0.88, CLOUD_DARK); drops(d, N * 0.3, N * 0.66, 3, N * 0.26, RAIN); save(img, "rain")

    img, d = canvas(); cloud(d, N * 0.06, N * 0.04, N * 0.88, CLOUD_DARK)
    d.polygon([(N * 0.55, N * 0.5), (N * 0.36, N * 0.76), (N * 0.5, N * 0.76), (N * 0.42, N * 0.98),
               (N * 0.68, N * 0.66), (N * 0.53, N * 0.66), (N * 0.62, N * 0.5)], fill=BOLT)
    save(img, "storm")

    img, d = canvas(); cloud(d, N * 0.06, N * 0.06, N * 0.88, CLOUD)
    for i in range(3):
        cx = N * (0.3 + i * 0.2)
        d.ellipse((cx - N * 0.05, N * 0.76, cx + N * 0.05, N * 0.86), fill=(240, 245, 255))
    save(img, "snow")

    for name, color in (("alert_warn", YELLOW), ("alert_crit", RED)):
        img, d = canvas()
        d.rounded_rectangle((0, 0, N - 1, N - 1), radius=0, fill=(0, 0, 0, 0))
        d.polygon([(N / 2, N * 0.06), (N * 0.96, N * 0.92), (N * 0.04, N * 0.92)], fill=color)
        d.rectangle((N * 0.455, N * 0.35, N * 0.545, N * 0.68), fill=(20, 20, 20))
        d.ellipse((N * 0.45, N * 0.74, N * 0.55, N * 0.84), fill=(20, 20, 20))
        save(img, name)

    print("icones gerados em", OUT)


if __name__ == "__main__":
    main()
