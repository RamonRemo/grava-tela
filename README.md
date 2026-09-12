<div align="center">

# 🎬 gravatui

**Record your screen on Wayland without lifting your hands off the keyboard.**

A terminal interface (curses, and clickable) on top of `grava-tela` — a lean
toggle over [gpu-screen-recorder](https://git.dec05eba.com/gpu-screen-recorder/).
Press it, recording starts. Press it again, it saves.

</div>

```
╭─ grava-tela ─────────────────────────────╮
│                                          │
│  ○ Pronto para gravar                    │
│                                          │
│  CAPTURAR                                │
│   r   ○ região (senão, tela toda)        │
│   a   ○ áudio do desktop                 │
│   m   ○ microfone                        │
│                                          │
│  Iniciar gravação                 espaço │
│                                          │
│  ~/Vídeos                                │
│                                          │
│   o  pasta   q  sair   x  apagar         │
╰──────────────────────────────────────────╯
```

> The TUI ships in Portuguese; the box above mirrors its real output.

---

## ✨ Features

- **One-key toggle** — starts and stops on the same key; saves the `.mp4` and
  fires a notification with a frame preview.
- **Clean, clickable TUI** — everything works by keyboard *or* mouse.
- **Real state** — the interface reads whether `gpu-screen-recorder` is actually
  running, not some made-up state.
- **Flexible targets** — the focused monitor or a mouse-selected region.
- **Optional audio** — desktop, microphone, both, or none.
- **Zero pip dependencies** — pure Python (stdlib only).

## 🧩 Anatomy

| Part | What it is |
|------|---------|
| **`grava-tela`** | The engine. Bash script, toggle. Records into `$XDG_VIDEOS_DIR` (or `~/Vídeos`), notifies with a preview. **Works on its own**, without the TUI. |
| **`gravatui.py`** (`grava-tui`) | The interface. Only assembles the flags and calls `grava-tela`; watches `gpu-screen-recorder` to know the state. |

## 📦 Dependencies

**Required**

| Package | What for |
|--------|---------|
| `gpu-screen-recorder` | The encoder. AMD / NVIDIA / Intel. Without it, nothing records. |
| `ffmpeg` | Generates the notification preview. |
| `python3` | Stdlib only (`curses`). No `pip`. |

**Optional**

| Package | Without it… |
|--------|----------|
| `slurp` | *region* mode does not work (the rest does). |
| `libnotify` (`notify-send`) | no start/stop notification. |
| `niri` + `jq` | **focused-monitor** detection falls back to the first monitor. |
| `kitty` | used by the `.desktop` launcher and the keybinding. |

### Installing the dependencies

```sh
# Arch / CachyOS
sudo pacman -S ffmpeg slurp libnotify jq

# Fedora
sudo dnf install ffmpeg slurp libnotify jq

# Debian / Ubuntu
sudo apt install ffmpeg slurp libnotify-bin jq
```

### What about gpu-screen-recorder?

It is **not** in the official repositories of most distros. Pick one:

```sh
# Arch / CachyOS (AUR)
paru -S gpu-screen-recorder

# Any distro — Flatpak (most portable)
flatpak install flathub com.dec05eba.gpu_screen_recorder
```

> ⚠️ Via **Flatpak** the binary is `flatpak run com.dec05eba.gpu_screen_recorder`,
> not `gpu-screen-recorder` on the PATH. In that case, expose a wrapper:
> ```sh
> printf '#!/bin/sh\nexec flatpak run com.dec05eba.gpu_screen_recorder "$@"\n' \
>   > ~/.local/bin/gpu-screen-recorder && chmod +x ~/.local/bin/gpu-screen-recorder
> ```

Build from source and docs: <https://git.dec05eba.com/gpu-screen-recorder/>.

## 🚀 Installation

```sh
git clone <url> gravatui && cd gravatui
./install.sh
```

`install.sh` is **idempotent** and:

- links `grava-tela` and `grava-tui` into `~/.local/bin`;
- installs the launcher into `~/.local/share/applications` (shows up in the app menu);
- checks the dependencies and reports what is missing.

Prefer not to install? Run it straight from the clone — `./gravatui.py` finds
`grava-tela` next to it.

## ⌨️ Usage

```sh
grava-tui                              # opens the TUI

grava-tela                             # records the focused monitor (toggle)
grava-tela --region --audio --mic      # region + desktop + microphone
grava-tela --stop                      # stop
```

In the TUI:

| Key | Action |
|-------|------|
| `r` / `a` / `m` | toggle region / audio / microphone |
| `space` | start or stop |
| `o` | open the recordings folder |
| `x` | delete the last video (asks for confirmation) |
| `q` | quit (does not interrupt an ongoing recording) |

All of this is also **clickable**.

## 🎯 Keybinding (niri)

A global shortcut can't be installed portably — every compositor has its own.
On **niri**, in `~/.config/niri/config.kdl` (or an included file):

```kdl
binds {
    Mod+Print hotkey-overlay-title="Gravar tela" {
        spawn "kitty" "--class" "gravatui" \
              "-o" "initial_window_width=48c" \
              "-o" "initial_window_height=20c" \
              "-o" "remember_window_size=no" \
              "-e" "grava-tui";
    }
}

window-rule {
    match app-id=r#"^gravatui$"#
    open-floating true
}
```

> 💡 `remember_window_size=no` is the trick: it's what makes kitty respect the
> size in cells. Without it, the window reopens at the remembered size and
> ignores `initial_window_width`.

Other compositors: point the shortcut at the same `kitty … -e grava-tui` command.

## ⚖️ Honest limitations

- **Focused monitor** uses `niri msg`. On another compositor, monitor mode falls
  back to the first output; **region** mode (slurp) works on any Wayland.
- It's **Wayland**. On X11 slurp does not run and the capture target changes.
- Tested with an **AMD** GPU. gpu-screen-recorder supports NVIDIA/Intel, but the
  parameters here were not exercised on those.

## 📄 License

[MIT](LICENSE).
