#!/usr/bin/env python3
# gravatui — TUI para o script grava-tela (gpu-screen-recorder no niri).
# Não regrava nada da lógica: só monta as flags e chama `grava-tela`.
#
# Teclas:
#   r  alvo: monitor focado <-> região (slurp)
#   a  áudio do desktop on/off
#   m  microfone on/off
#   espaço / enter   iniciar (ou parar, se já estiver gravando)
#   s  parar
#   o  abrir a pasta de gravações
#   q  sair (não interrompe uma gravação em andamento)

import curses
import os
import shutil
import subprocess
import time

def _find_grava():
    # 1) variável de ambiente explícita  2) PATH  3) ao lado deste arquivo
    #    (permite rodar direto do repositório clonado, antes de instalar)
    env = os.environ.get("GRAVA_TELA")
    if env and os.path.exists(env):
        return env
    found = shutil.which("grava-tela")
    if found:
        return found
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grava-tela")
    if os.path.exists(here):
        return here
    return os.path.expanduser("~/.local/bin/grava-tela")


GRAVA = _find_grava()


def videos_dir():
    d = os.path.expanduser("~/.config/user-dirs.dirs")
    out = os.environ.get("XDG_VIDEOS_DIR")
    if not out and os.path.isfile(d):
        try:
            with open(d) as f:
                for line in f:
                    if line.startswith("XDG_VIDEOS_DIR"):
                        val = line.split("=", 1)[1].strip().strip('"')
                        out = val.replace("$HOME", os.path.expanduser("~"))
        except OSError:
            pass
    return out or os.path.expanduser("~/Vídeos")


def is_recording():
    return subprocess.run(
        ["pgrep", "-f", "^gpu-screen-recorder"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0


def rec_start_epoch():
    # início da gravação = start time do processo gpu-screen-recorder
    r = subprocess.run(
        ["pgrep", "-f", "^gpu-screen-recorder"],
        capture_output=True, text=True,
    )
    pid = r.stdout.split()[0] if r.stdout.split() else None
    if not pid:
        return None
    try:
        e = subprocess.run(
            ["ps", "-o", "etimes=", "-p", pid],
            capture_output=True, text=True,
        )
        return time.time() - int(e.stdout.strip())
    except (ValueError, IndexError):
        return None


def fmt_elapsed(secs):
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class UI:
    def __init__(self):
        self.region = False
        self.audio = False
        self.mic = False
        self.msg = ""
        self.msg_until = 0.0

    def flash(self, text, secs=4):
        self.msg = text
        self.msg_until = time.time() + secs

    def flags(self):
        f = []
        if self.region:
            f.append("--region")
        if self.audio:
            f.append("--audio")
        if self.mic:
            f.append("--mic")
        return f

    def run_grava(self, extra=None):
        if not os.path.exists(GRAVA):
            self.flash("grava-tela não encontrado no PATH")
            return
        args = [GRAVA] + (extra if extra is not None else self.flags())
        subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def toggle(self, rec):
        # espelha o comportamento do próprio script (é um toggle)
        if rec:
            self.run_grava(["--stop"])
            self.flash("parando gravação…")
        else:
            self.run_grava()
            alvo = "região (slurp)" if self.region else "monitor focado"
            self.flash(f"iniciando: {alvo}…")


def draw(stdscr, ui):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(250)

    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # gravando / on
        curses.init_pair(2, curses.COLOR_RED, -1)     # rec dot
        curses.init_pair(3, curses.COLOR_CYAN, -1)    # títulos
        curses.init_pair(4, curses.COLOR_YELLOW, -1)  # mensagens
        curses.init_pair(5, curses.COLOR_WHITE, -1)

    C_ON = curses.color_pair(1) | curses.A_BOLD
    C_REC = curses.color_pair(2) | curses.A_BOLD
    C_TITLE = curses.color_pair(3) | curses.A_BOLD
    C_MSG = curses.color_pair(4)
    C_DIM = curses.A_DIM

    curses.mousemask(curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED)
    try:
        # sem atraso: clique responde na hora em vez de virar sequência de escape
        curses.set_escdelay(25)
    except (AttributeError, curses.error):
        pass

    outdir = videos_dir()

    def put(y, x, s, attr=0):
        # addstr tolerante: nunca estoura a borda da janela
        h, w = stdscr.getmaxyx()
        if 0 <= y < h and x < w:
            try:
                stdscr.addstr(y, x, s[: w - x - 1], attr)
            except curses.error:
                pass

    while True:
        rec = is_recording()
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        bw = min(w - 2, 44)          # largura do card
        bx = max(0, (w - bw) // 2)   # centraliza na horizontal
        by = 1
        ix = bx + 3                  # margem interna do conteúdo
        inner = bw - 4

        # ── moldura ──
        put(by, bx, "╭─ ", C_DIM)
        put(by, bx + 3, "grava-tela", C_TITLE)
        put(by, bx + 13, " " + "─" * (bw - 15) + "╮", C_DIM)
        for row in range(by + 1, by + 16):
            put(row, bx, "│", C_DIM)
            put(row, bx + bw - 1, "│", C_DIM)
        put(by + 16, bx, "╰" + "─" * (bw - 2) + "╯", C_DIM)

        zones = {}  # y -> (x_ini, x_fim, action)

        # ── estado ──
        sy = by + 2
        if rec:
            start = rec_start_epoch()
            el = fmt_elapsed(time.time() - start) if start else "--:--"
            put(sy, ix, "●", C_REC)
            put(sy, ix + 2, "Gravando", C_REC)
            put(sy, bx + bw - 3 - len(el), el, C_ON)
        else:
            put(sy, ix, "○", C_DIM)
            put(sy, ix + 2, "Pronto para gravar", C_DIM)

        # ── seção capturar ──
        def toggle_row(y, key, on, label, action, locked=False):
            cap_attr = curses.A_REVERSE | (0 if locked else curses.A_BOLD)
            glyph, gattr = ("◉", C_ON) if on else ("○", C_DIM if locked else 0)
            put(y, ix, f" {key} ", C_DIM if locked else cap_attr)
            put(y, ix + 5, glyph, gattr)
            put(y, ix + 7, label, C_DIM if locked else (C_ON if on else 0))
            if not locked:
                zones[y] = (ix, ix + 7 + len(label), action)

        put(by + 4, ix, "CAPTURAR", C_TITLE)
        toggle_row(by + 5, "r", ui.region, "região (senão, tela toda)", "region", rec)
        toggle_row(by + 6, "a", ui.audio, "áudio do desktop", "audio", rec)
        toggle_row(by + 7, "m", ui.mic, "microfone", "mic", rec)

        # ── botão principal ──
        btn_y = by + 9
        if rec:
            txt, battr = "Parar gravação", curses.color_pair(2) | curses.A_REVERSE | curses.A_BOLD
        else:
            txt, battr = "Iniciar gravação", curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD
        hint = "espaço"
        barw = bw - 3  # cabe exatamente entre as bordas (bx+2 .. bx+bw-2)
        pad = max(1, barw - 2 - len(txt) - len(hint))
        bar = (" " + txt + " " * pad + hint + " ")[:barw].ljust(barw)
        put(btn_y, bx + 2, bar, battr)
        zones[btn_y] = (bx + 2, bx + bw - 2, "toggle")

        # ── rodapé ──
        fy = by + 11
        put(fy, ix, outdir.replace(os.path.expanduser("~"), "~")[:inner], C_DIM)

        gy = by + 13
        put(gy, ix, " o ", curses.A_REVERSE)
        put(gy, ix + 4, "pasta", C_DIM)
        zone_pasta = (gy, ix, ix + 9, "open")
        put(gy, ix + 12, " q ", curses.A_REVERSE)
        put(gy, ix + 16, "sair", C_DIM)
        zone_sair = (gy, ix + 12, ix + 20, "quit")

        # ── mensagem efêmera ──
        if ui.msg and time.time() < ui.msg_until:
            put(by + 14, ix, ui.msg[:inner], C_MSG)

        stdscr.refresh()

        try:
            ch = stdscr.getch()
        except curses.error:
            ch = -1
        if ch == -1:
            continue

        action = None
        if ch == curses.KEY_MOUSE:
            try:
                _, mx, my, _, _ = curses.getmouse()
            except curses.error:
                continue
            if my in zones:
                x0, x1, a = zones[my]
                if x0 <= mx <= x1:
                    action = a
            if action is None:
                for zy, x0, x1, a in (zone_pasta, zone_sair):
                    if my == zy and x0 <= mx <= x1:
                        action = a
                        break
            if action is None:
                continue
        else:
            k = chr(ch).lower() if 0 <= ch < 256 else ""
            if k == "q":
                action = "quit"
            elif k == "r":
                action = "region"
            elif k == "a":
                action = "audio"
            elif k == "m":
                action = "mic"
            elif ch in (ord(" "), curses.KEY_ENTER, 10, 13):
                action = "toggle"
            elif k == "s":
                action = "stop"
            elif k == "o":
                action = "open"

        if action == "quit":
            return
        elif action == "region" and not rec:
            ui.region = not ui.region
        elif action == "audio" and not rec:
            ui.audio = not ui.audio
        elif action == "mic" and not rec:
            ui.mic = not ui.mic
        elif action == "toggle":
            ui.toggle(rec)
            time.sleep(0.4)
        elif action == "stop":
            if rec:
                ui.run_grava(["--stop"])
                ui.flash("parando gravação…")
            else:
                ui.flash("nada gravando")
        elif action == "open":
            subprocess.Popen(
                ["xdg-open", outdir],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            ui.flash("abrindo pasta…")


def main():
    if not os.path.exists(GRAVA):
        print("grava-tela não encontrado em ~/.local/bin nem no PATH.")
        return 1
    curses.wrapper(draw, UI())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
