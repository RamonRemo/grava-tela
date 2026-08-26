<div align="center">

# 🎬 gravatui

**Grave a tela no Wayland sem tirar a mão do teclado.**

Uma interface de terminal (curses, e clicável) por cima do `grava-tela` — um
toggle enxuto sobre o [gpu-screen-recorder](https://git.dec05eba.com/gpu-screen-recorder/).
Aperta, grava. Aperta de novo, salva.

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
│   o  pasta    q  sair                    │
╰──────────────────────────────────────────╯
```

---

## ✨ Recursos

- **Toggle de um toque** — inicia e para na mesma tecla; salva o `.mp4` e manda
  uma notificação com preview do frame.
- **TUI limpa e clicável** — tudo funciona por teclado *ou* mouse.
- **Estado real** — a interface lê se o `gpu-screen-recorder` está de fato
  rodando, não um estado inventado.
- **Alvos flexíveis** — monitor focado ou uma região selecionada com o mouse.
- **Áudio opcional** — desktop, microfone, os dois, ou nada.
- **Zero dependência de pip** — Python puro (só a stdlib).

## 🧩 Anatomia

| Peça | O que é |
|------|---------|
| **`grava-tela`** | O motor. Script bash, toggle. Grava em `$XDG_VIDEOS_DIR` (ou `~/Vídeos`), notifica com preview. **Funciona sozinho**, sem a TUI. |
| **`gravatui.py`** (`grava-tui`) | A interface. Só monta as flags e chama o `grava-tela`; observa o `gpu-screen-recorder` pra saber o estado. |

## 📦 Dependências

**Obrigatórias**

| Pacote | Pra quê |
|--------|---------|
| `gpu-screen-recorder` | O encoder. AMD / NVIDIA / Intel. Sem ele, nada grava. |
| `ffmpeg` | Gera o preview da notificação. |
| `python3` | Só a stdlib (`curses`). Nada de `pip`. |

**Opcionais**

| Pacote | Sem ele… |
|--------|----------|
| `slurp` | o modo *região* não funciona (o resto sim). |
| `libnotify` (`notify-send`) | sem notificação de início/fim. |
| `niri` + `jq` | a detecção do **monitor focado** cai no primeiro monitor. |
| `kitty` | usado pelo lançador `.desktop` e pelo atalho de teclado. |

### Instalando as dependências

```sh
# Arch / CachyOS
sudo pacman -S ffmpeg slurp libnotify jq

# Fedora
sudo dnf install ffmpeg slurp libnotify jq

# Debian / Ubuntu
sudo apt install ffmpeg slurp libnotify-bin jq
```

### E o gpu-screen-recorder?

Ele **não está** nos repositórios oficiais da maioria das distros. Escolha um:

```sh
# Arch / CachyOS (AUR)
paru -S gpu-screen-recorder

# Qualquer distro — Flatpak (mais portável)
flatpak install flathub com.dec05eba.gpu_screen_recorder
```

> ⚠️ Pela **Flatpak** o binário é `flatpak run com.dec05eba.gpu_screen_recorder`,
> não `gpu-screen-recorder` no PATH. Nesse caso, exponha um wrapper:
> ```sh
> printf '#!/bin/sh\nexec flatpak run com.dec05eba.gpu_screen_recorder "$@"\n' \
>   > ~/.local/bin/gpu-screen-recorder && chmod +x ~/.local/bin/gpu-screen-recorder
> ```

Build a partir do fonte e docs: <https://git.dec05eba.com/gpu-screen-recorder/>.

## 🚀 Instalação

```sh
git clone <url> gravatui && cd gravatui
./install.sh
```

O `install.sh` é **idempotente** e faz:

- linka `grava-tela` e `grava-tui` em `~/.local/bin`;
- instala o lançador em `~/.local/share/applications` (aparece no menu de apps);
- confere as dependências e diz o que falta.

Prefere não instalar? Roda direto do clone — `./gravatui.py` acha o `grava-tela`
ao lado dele.

## ⌨️ Uso

```sh
grava-tui                              # abre a TUI

grava-tela                             # grava o monitor focado (toggle)
grava-tela --region --audio --mic      # região + desktop + microfone
grava-tela --stop                      # para
```

Na TUI:

| Tecla | Ação |
|-------|------|
| `r` / `a` / `m` | alterna região / áudio / microfone |
| `espaço` | inicia ou para |
| `o` | abre a pasta de gravações |
| `q` | sai (não interrompe a gravação) |

Tudo isso também é **clicável**.

## 🎯 Atalho de teclado (niri)

Atalho global não dá pra instalar de forma portável — cada compositor tem o seu.
No **niri**, em `~/.config/niri/config.kdl` (ou num arquivo incluído):

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

> 💡 O `remember_window_size=no` é o pulo do gato: é ele que faz o kitty
> respeitar o tamanho em células. Sem ele, a janela reabre no tamanho lembrado
> e ignora o `initial_window_width`.

Outros compositores: aponte o atalho pro mesmo comando `kitty … -e grava-tui`.

## ⚖️ Limitações honestas

- **Monitor focado** usa `niri msg`. Em outro compositor, o modo monitor cai no
  primeiro output; o modo **região** (slurp) funciona em qualquer Wayland.
- É **Wayland**. Em X11 o slurp não roda e o alvo de captura muda.
- Testado com GPU **AMD**. O gpu-screen-recorder suporta NVIDIA/Intel, mas os
  parâmetros aqui não foram exercitados nessas.

## 📄 Licença

[MIT](LICENSE).
