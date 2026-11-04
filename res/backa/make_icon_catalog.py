# Gera a biblioteca de ícones do editor (res/backa/tabler-icons) a partir do Tabler Icons (https://tabler.io/icons, licença MIT).
#
# Uso: baixe para uma pasta os arquivos abaixo (mesma versão) e rode:
#   .venv\Scripts\python.exe res\backa\make_icon_catalog.py <pasta> <versão>
#   - icons.json              -> https://cdn.jsdelivr.net/npm/@tabler/icons@<versão>/icons.json
#   - LICENSE                 -> https://cdn.jsdelivr.net/npm/@tabler/icons@<versão>/LICENSE
#   - tabler-icons.ttf        -> https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@<versão>/dist/fonts/tabler-icons.ttf
#   - tabler-icons-filled.ttf -> https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@<versão>/dist/fonts/tabler-icons-filled.ttf
#
# O catálogo (catalog.json) guarda, para cada ícone, o caractere nas fontes de contorno e preenchida e as palavras de busca.
# A lista "suggested" é a seleção que aparece primeiro no editor, com nomes em português (também usados na busca).
import json
import shutil
import sys
from pathlib import Path

from PIL import ImageFont

OUT = Path(__file__).resolve().parent / "tabler-icons"

SUGGESTED = [
    ("Hardware", [
        ("cpu", "processador"), ("cpu-2", "processador chip"), ("gpu", "placa de vídeo"), ("gpu-2", "placa de vídeo"),
        ("device-desktop", "computador monitor pc"), ("device-laptop", "notebook"), ("server", "servidor"),
        ("database", "disco armazenamento"), ("device-floppy", "disquete ssd salvar"), ("device-sd-card", "memória ram cartão"),
        ("keyboard", "teclado"), ("mouse", "mouse"), ("headphones", "fone de ouvido headset"), ("microphone", "microfone"),
        ("volume", "som volume"), ("device-tv", "tv televisão"), ("device-mobile", "celular"),
        ("car-fan", "ventoinha cooler fan"), ("propeller", "ventoinha hélice"),
    ]),
    ("Medidas", [
        ("temperature", "temperatura"), ("temperature-celsius", "graus celsius"), ("flame", "fogo quente"),
        ("snowflake", "frio gelo"), ("droplet", "água líquido water cooler"), ("gauge", "medidor velocímetro"),
        ("dashboard", "painel"), ("activity", "atividade uso"), ("activity-heartbeat", "batimento"),
        ("chart-line", "gráfico de linha"), ("chart-bar", "gráfico de barras"), ("chart-pie", "gráfico de pizza"),
        ("bolt", "energia raio potência watts"), ("plug", "tomada energia"), ("battery-4", "bateria"), ("power", "ligar desligar"),
    ]),
    ("Rede", [
        ("wifi", "wi-fi internet sem fio"), ("network", "rede"), ("world", "internet mundo"), ("router", "roteador"),
        ("antenna", "antena"), ("download", "baixar download"), ("upload", "enviar upload"), ("arrows-down-up", "tráfego"),
        ("cloud-download", "nuvem baixar"), ("cloud-upload", "nuvem enviar"), ("plug-connected", "cabo conectado ethernet"),
        ("bluetooth", "bluetooth"), ("broadcast", "transmissão"),
    ]),
    ("Jogos e mídia", [
        ("device-gamepad-2", "controle jogo game"), ("device-gamepad", "controle jogo game"), ("device-nintendo", "nintendo"),
        ("playstation-triangle", "playstation"), ("brand-xbox", "xbox"), ("brand-steam", "steam"), ("trophy", "troféu"),
        ("target", "alvo mira"), ("crosshair", "mira"), ("sword", "espada"), ("rocket", "foguete"), ("ghost", "fantasma"),
        ("skull", "caveira"), ("music", "música"), ("player-play", "play reproduzir"), ("movie", "filme"),
        ("photo", "foto imagem"), ("camera", "câmera"),
    ]),
    ("Marcas e programas", [
        ("brand-windows", "windows"), ("brand-ubuntu", "linux ubuntu"), ("brand-github", "github"), ("brand-docker", "docker"),
        ("brand-python", "python"), ("brand-discord", "discord"), ("brand-spotify", "spotify"), ("brand-twitch", "twitch"),
        ("brand-youtube", "youtube"), ("brand-chrome", "chrome navegador"), ("brand-firefox", "firefox navegador"),
        ("terminal-2", "terminal"), ("code", "código programação"), ("bug", "bug erro"),
    ]),
    ("Clima e tempo", [
        ("sun", "sol"), ("moon", "lua noite"), ("cloud", "nuvem nublado"), ("cloud-rain", "chuva"), ("cloud-storm", "tempestade"),
        ("cloud-snow", "neve"), ("cloud-fog", "neblina"), ("wind", "vento"), ("umbrella", "guarda-chuva"),
        ("sunrise", "nascer do sol"), ("sunset", "pôr do sol"), ("clock", "relógio hora"), ("calendar", "calendário data"),
        ("alarm", "alarme despertador"), ("hourglass", "ampulheta tempo ligado"),
    ]),
    ("Status e outros", [
        ("alert-triangle", "alerta atenção aviso"), ("alert-circle", "alerta"), ("circle-check", "ok certo"),
        ("info-circle", "informação"), ("shield-check", "segurança proteção"), ("lock", "cadeado"), ("bell", "sino notificação"),
        ("heart", "coração"), ("star", "estrela"), ("home", "casa"), ("user", "usuário pessoa"),
        ("settings", "configurações engrenagem"), ("adjustments", "ajustes"), ("tool", "ferramenta"), ("refresh", "atualizar"),
        ("eye", "olho"), ("coffee", "café"), ("pizza", "pizza"),
    ]),
]


def main(src: Path, version: str):
    meta = json.loads((src / "icons.json").read_text(encoding="utf-8"))
    outline = ImageFont.truetype(str(src / "tabler-icons.ttf"), 32)
    filled = ImageFont.truetype(str(src / "tabler-icons-filled.ttf"), 32)

    def code(font, info):
        cp = int(info["unicode"], 16)
        return cp if font.getmask(chr(cp)).getbbox() else 0

    pt = {name: words for _, group in SUGGESTED for name, words in group}
    icons = {}
    for name, v in sorted(meta.items()):
        styles = v.get("styles", {})
        o = code(outline, styles["outline"]) if "outline" in styles else 0
        f = code(filled, styles["filled"]) if "filled" in styles else 0
        if not (o or f):
            continue
        words = [name.replace("-", " "), str(v.get("category") or "")] + [str(t) for t in v.get("tags", [])]
        if name in pt:
            words.insert(0, pt[name])
        icons[name] = [o, f, " ".join(w for w in words if w).lower()]

    missing = [n for _, g in SUGGESTED for n, _ in g if n not in icons]
    if missing:
        raise SystemExit(f"Ícones sugeridos que não existem nesta versão: {missing}")

    OUT.mkdir(exist_ok=True)
    catalog = {"version": version, "suggested": [[g, [n for n, _ in items]] for g, items in SUGGESTED], "icons": icons}
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for f in ("tabler-icons.ttf", "tabler-icons-filled.ttf", "LICENSE"):
        shutil.copyfile(src / f, OUT / f)
    print(f"{len(icons)} ícones ({sum(1 for v in icons.values() if v[1])} com versão preenchida) -> {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
