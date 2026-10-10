if [ -n "${BASH_VERSION:-}" ] && [ "$(tty 2>/dev/null || true)" = "/dev/tty1" ]; then
    exec /usr/local/bin/battery-os
fi