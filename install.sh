#!/usr/bin/env bash
# Instala o gravatui: linka os executáveis em ~/.local/bin e o lançador .desktop.
# Idempotente — pode rodar de novo sem quebrar nada.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${XDG_BIN_HOME:-$HOME/.local/bin}"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

mkdir -p "$BIN" "$APPS"

echo "==> linkando executáveis em $BIN"
ln -sf "$REPO/grava-tela"  "$BIN/grava-tela"
ln -sf "$REPO/gravatui.py" "$BIN/grava-tui"
chmod +x "$REPO/grava-tela" "$REPO/gravatui.py"

echo "==> instalando lançador em $APPS"
sed "s#@REPO@#$REPO#g" "$REPO/gravatui.desktop" > "$APPS/gravatui.desktop"

# Checagem de dependências (não aborta; só avisa)
echo "==> dependências:"
req=(gpu-screen-recorder ffmpeg)
opt=(slurp notify-send jq niri kitty)
miss=()
for c in "${req[@]}"; do
  if command -v "$c" >/dev/null; then echo "  ok   $c"; else echo "  FALTA $c (obrigatório)"; miss+=("$c"); fi
done
for c in "${opt[@]}"; do
  command -v "$c" >/dev/null && echo "  ok   $c" || echo "  --   $c (opcional)"
done

case ":$PATH:" in
  *":$BIN:"*) : ;;
  *) echo "!! $BIN não está no PATH — adicione ao seu shell rc" ;;
esac

echo
echo "Pronto. Rode 'grava-tui' ou abra 'Gravar tela' no menu de apps."
echo "No niri, para o atalho Super+Print veja a seção 'Atalho' do README."
[ ${#miss[@]} -eq 0 ] || { echo; echo "Instale o que falta antes de usar: ${miss[*]}"; }
