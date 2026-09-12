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
#   x  apagar o último vídeo (pede confirmação)
#   q  sair (não interrompe uma gravação em andamento)
#
# Clique no caminho da pasta (sublinhado) para escolher outro diretório de
# saída (zenity/kdialog). O idioma (pt/en) vem do locale do sistema
# ($LC_ALL/$LANG); qualquer coisa que não seja pt cai no inglês (default).

import curses
import glob
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


def detect_lang():
    # generic: honour the standard locale env (LC_ALL > LC_MESSAGES > LANG >
    # LANGUAGE). niri/noctalia inherit this env, so nothing WM-specific is
    # needed. anything that isn't Portuguese falls back to English.
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        v = os.environ.get(var, "")
        if v:
            code = v.split(":")[0].split(".")[0].split("_")[0].lower()
            if code:
                return "pt" if code == "pt" else "en"
    return "en"


STRINGS = {
    "en": {
        "ready": "Ready to record",
        "recording": "Recording",
        "capture": "CAPTURE",
        "region": "region (else full screen)",
        "audio": "desktop audio",
        "mic": "microphone",
        "start": "Start recording",
        "stop": "Stop recording",
        "space": "space",
        "folder": "folder",
        "quit": "quit",
        "delete": "delete",
        "confirm": "Delete {name}?",
        "yes": "yes",
        "no": "no",
        "not_found": "grava-tela not found on PATH",
        "stopping": "stopping recording…",
        "starting": "starting: {target}…",
        "tgt_region": "region (slurp)",
        "tgt_monitor": "focused monitor",
        "nothing": "nothing recording",
        "opening": "opening folder…",
        "no_fm": "no file manager found",
        "stop_first": "stop the recording before deleting",
        "no_video": "no video to delete",
        "deleted": "deleted: {name}",
        "del_fail": "delete failed",
        "canceled": "canceled",
        "folder_set": "folder: {dir}",
        "no_picker": "no folder picker (install zenity or kdialog)",
        "main_not_found": "grava-tela not found in ~/.local/bin or on PATH.",
    },
    "pt": {
        "ready": "Pronto para gravar",
        "recording": "Gravando",
        "capture": "CAPTURAR",
        "region": "região (senão, tela toda)",
        "audio": "áudio do desktop",
        "mic": "microfone",
        "start": "Iniciar gravação",
        "stop": "Parar gravação",
        "space": "espaço",
        "folder": "pasta",
        "quit": "sair",
        "delete": "apagar",
        "confirm": "Apagar {name}?",
        "yes": "sim",
        "no": "não",
        "not_found": "grava-tela não encontrado no PATH",
        "stopping": "parando gravação…",
        "starting": "iniciando: {target}…",
        "tgt_region": "região (slurp)",
        "tgt_monitor": "monitor focado",
        "nothing": "nada gravando",
        "opening": "abrindo pasta…",
        "no_fm": "nenhum gerenciador de arquivos encontrado",
        "stop_first": "pare a gravação antes de apagar",
        "no_video": "nenhum vídeo para apagar",
        "deleted": "apagado: {name}",
        "del_fail": "falha ao apagar",
        "canceled": "cancelado",
        "folder_set": "pasta: {dir}",
        "no_picker": "sem seletor de pasta (instale zenity ou kdialog)",
        "main_not_found": "grava-tela não encontrado em ~/.local/bin nem no PATH.",
    },
}


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


# file managers we try, in order, before falling back to gio/xdg-open.
# opening one of these directly is more reliable than xdg-open, whose
# inode/directory handler can be misconfigured and open the wrong app.
FILE_MANAGERS = ("nautilus", "dolphin", "nemo", "thunar", "pcmanfm-qt", "pcmanfm", "caja")


def open_folder(path):
    # detached (start_new_session): closing gravatui never SIGHUPs the file
    # manager, so it keeps living after the TUI's terminal goes away.
    opener = None
    for fm in FILE_MANAGERS:
        if shutil.which(fm):
            opener = [fm, path]
            break
    if opener is None:
        if shutil.which("gio"):
            opener = ["gio", "open", path]
        elif shutil.which("xdg-open"):
            opener = ["xdg-open", path]
    if opener is None:
        return False
    subprocess.Popen(
        opener,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True


def last_video(outdir):
    # newest grav-*.mp4 by mtime; None if the folder has none yet.
    vids = glob.glob(os.path.join(outdir, "grav-*.mp4"))
    if not vids:
        return None
    return max(vids, key=os.path.getmtime)


def delete_video(path):
    # removes the .mp4 and its leftover -preview.png, if any. returns True on success.
    try:
        os.remove(path)
    except OSError:
        return False
    preview = path[:-4] + "-preview.png" if path.endswith(".mp4") else path + "-preview.png"
    try:
        os.remove(preview)
    except OSError:
        pass
    return True


def pick_folder(start):
    # GUI directory chooser. returns: chosen path (str), None if canceled,
    # or False if no picker is installed. blocks until the dialog closes.
    if shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", "--directory",
               "--title=grava-tela", "--filename", start.rstrip("/") + "/"]
    elif shutil.which("kdialog"):
        cmd = ["kdialog", "--getexistingdirectory", start]
    else:
        return False
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except OSError:
        return None
    if r.returncode != 0:
        return None
    d = r.stdout.strip()
    return d if d and os.path.isdir(d) else None


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
        self.confirm_del = None   # path pending delete confirmation, or None
        self.t = STRINGS[detect_lang()]
        self.outdir = videos_dir()   # mutável pelo seletor de pasta

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
        f.append("--outdir=" + self.outdir)
        return f

    def run_grava(self, extra=None):
        if not os.path.exists(GRAVA):
            self.flash(self.t["not_found"])
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
            self.flash(self.t["stopping"])
        else:
            self.run_grava()
            target = self.t["tgt_region"] if self.region else self.t["tgt_monitor"]
            self.flash(self.t["starting"].format(target=target))


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

    t = ui.t

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
        lastvid = last_video(ui.outdir)
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
            put(sy, ix + 2, t["recording"], C_REC)
            put(sy, bx + bw - 3 - len(el), el, C_ON)
        else:
            put(sy, ix, "○", C_DIM)
            put(sy, ix + 2, t["ready"], C_DIM)

        # ── seção capturar ──
        def toggle_row(y, key, on, label, action, locked=False):
            cap_attr = curses.A_REVERSE | (0 if locked else curses.A_BOLD)
            glyph, gattr = ("◉", C_ON) if on else ("○", C_DIM if locked else 0)
            put(y, ix, f" {key} ", C_DIM if locked else cap_attr)
            put(y, ix + 5, glyph, gattr)
            put(y, ix + 7, label, C_DIM if locked else (C_ON if on else 0))
            if not locked:
                zones[y] = (ix, ix + 7 + len(label), action)

        put(by + 4, ix, t["capture"], C_TITLE)
        toggle_row(by + 5, "r", ui.region, t["region"], "region", rec)
        toggle_row(by + 6, "a", ui.audio, t["audio"], "audio", rec)
        toggle_row(by + 7, "m", ui.mic, t["mic"], "mic", rec)

        # ── botão principal ──
        btn_y = by + 9
        if rec:
            txt, battr = t["stop"], curses.color_pair(2) | curses.A_REVERSE | curses.A_BOLD
        else:
            txt, battr = t["start"], curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD
        hint = t["space"]
        barw = bw - 3  # cabe exatamente entre as bordas (bx+2 .. bx+bw-2)
        pad = max(1, barw - 2 - len(txt) - len(hint))
        bar = (" " + txt + " " * pad + hint + " ")[:barw].ljust(barw)
        put(btn_y, bx + 2, bar, battr)
        zones[btn_y] = (bx + 2, bx + bw - 2, "toggle")

        # ── rodapé ──
        # caminho da pasta: clicável → abre um seletor de diretório
        fy = by + 11
        shown = ui.outdir.replace(os.path.expanduser("~"), "~")[:inner]
        put(fy, ix, shown, C_DIM | curses.A_UNDERLINE)

        gy = by + 13
        put(gy, ix, " o ", curses.A_REVERSE)
        put(gy, ix + 4, t["folder"], C_DIM)
        put(gy, ix + 12, " q ", curses.A_REVERSE)
        put(gy, ix + 16, t["quit"], C_DIM)
        extra_zones = [
            (fy, ix, ix + len(shown), "pick"),
            (gy, ix, ix + 9, "open"),
            (gy, ix + 12, ix + 20, "quit"),
        ]

        # botão apagar: só fora de gravação e quando existe pelo menos um vídeo.
        # escondido durante a confirmação (é o próprio alvo).
        if not rec and lastvid and not ui.confirm_del:
            put(gy, ix + 22, " x ", curses.A_REVERSE)
            put(gy, ix + 26, t["delete"], C_DIM)
            extra_zones.append((gy, ix + 22, ix + 32, "del_ask"))

        # ── confirmação de apagar / mensagem efêmera ──
        if ui.confirm_del:
            name = os.path.basename(ui.confirm_del)
            put(by + 14, ix, t["confirm"].format(name=name)[:inner], C_REC)
            put(by + 15, ix, f" {t['yes'][0]} ", curses.A_REVERSE)
            put(by + 15, ix + 4, t["yes"], C_ON)
            put(by + 15, ix + 10, f" {t['no'][0]} ", curses.A_REVERSE)
            put(by + 15, ix + 14, t["no"], C_DIM)
            extra_zones.append((by + 15, ix, ix + 8, "del_yes"))
            extra_zones.append((by + 15, ix + 10, ix + 18, "del_no"))
        elif ui.msg and time.time() < ui.msg_until:
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
                for zy, x0, x1, a in extra_zones:
                    if my == zy and x0 <= mx <= x1:
                        action = a
                        break
            if action is None:
                continue
        else:
            k = chr(ch).lower() if 0 <= ch < 256 else ""
            if ui.confirm_del:
                # em confirmação: s/y/enter = sim, n/q/esc = não, resto ignora
                if k in ("s", "y") or ch in (curses.KEY_ENTER, 10, 13):
                    action = "del_yes"
                elif k in ("n", "q") or ch == 27:
                    action = "del_no"
            elif k == "q":
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
            elif k == "x":
                action = "del_ask"

        # durante confirmação, nada além de responder sim/não
        if ui.confirm_del and action not in ("del_yes", "del_no"):
            continue

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
                ui.flash(t["stopping"])
            else:
                ui.flash(t["nothing"])
        elif action == "open":
            if open_folder(ui.outdir):
                ui.flash(t["opening"])
            else:
                ui.flash(t["no_fm"])
        elif action == "pick":
            res = pick_folder(ui.outdir)
            if res is False:
                ui.flash(t["no_picker"])
            elif res:
                ui.outdir = res
                ui.flash(t["folder_set"].format(
                    dir=res.replace(os.path.expanduser("~"), "~")))
        elif action == "del_ask":
            if rec:
                ui.flash(t["stop_first"])
            elif lastvid:
                ui.confirm_del = lastvid
            else:
                ui.flash(t["no_video"])
        elif action == "del_yes":
            target = ui.confirm_del
            ui.confirm_del = None
            if target and delete_video(target):
                ui.flash(t["deleted"].format(name=os.path.basename(target)))
            else:
                ui.flash(t["del_fail"])
        elif action == "del_no":
            ui.confirm_del = None
            ui.flash(t["canceled"])


def main():
    if not os.path.exists(GRAVA):
        print(STRINGS[detect_lang()]["main_not_found"])
        return 1
    curses.wrapper(draw, UI())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
