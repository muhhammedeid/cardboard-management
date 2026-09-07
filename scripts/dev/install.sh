#!/usr/bin/env bash
# install.sh — expose cardboard-start / cardboard-stop as global commands.
#
# Creates symlinks in ~/.local/bin, which is already added to PATH by
# ~/.profile on this system. No shell configuration is modified.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$BIN_DIR"
for cmd in cardboard-start cardboard-stop; do
	ln -sfn "$SCRIPT_DIR/$cmd" "$BIN_DIR/$cmd"
	echo "installed: $BIN_DIR/$cmd -> $SCRIPT_DIR/$cmd"
done

case ":$PATH:" in
*":$BIN_DIR:"*) ;;
*)
	echo "NOTE: $BIN_DIR is not on this shell's PATH."
	echo "      '~/.profile' already adds it for new login shells; open a new shell or run:"
	echo "      export PATH=\"$BIN_DIR:\$PATH\""
	;;
esac

echo "Done. Run 'cardboard-start' from any directory."
