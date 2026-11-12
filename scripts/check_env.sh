#!/usr/bin/env bash
# CallBuddy environment check (macOS). READ-ONLY: it installs nothing and changes nothing.
# Run:  bash check_env.sh   then paste the output back in the thread.
# It never prints API keys: it only says whether a .env file exists, not what is in it.

line() { printf '%-16s %s\n' "$1" "$2"; }
have() { command -v "$1" >/dev/null 2>&1; }

echo "=== CallBuddy environment check ==="
line "OS"        "$(sw_vers -productName 2>/dev/null) $(sw_vers -productVersion 2>/dev/null) ($(uname -m))"
line "CPU"       "$(sysctl -n machdep.cpu.brand_string 2>/dev/null), $(sysctl -n hw.ncpu) cores"
line "RAM"       "$(( $(sysctl -n hw.memsize) / 1073741824 )) GB"
line "Free disk" "$(df -h ~ | awk 'NR==2{print $4}') on home volume"
line "Shell"     "$SHELL"
line "Xcode CLT" "$(xcode-select -p 2>/dev/null || echo MISSING)"
line "Homebrew"  "$(have brew && brew --version | head -1 || echo MISSING)"
line "git"       "$(have git && git --version || echo MISSING)"
line "git user"  "$(git config --global user.name 2>/dev/null || echo 'not set') <$(git config --global user.email 2>/dev/null || echo 'not set')>"
line "python3"   "$(have python3 && python3 --version 2>&1) at $(command -v python3 2>/dev/null)"
for v in 3.11 3.12 3.13; do have "python$v" && line "python$v" "$(command -v python$v)"; done
line "uv"        "$(have uv && uv --version || echo MISSING)"
have uv && line "uv pythons" "$(uv python list --only-installed 2>/dev/null | awk '{print $1}' | tr '\n' ' ')"
line "gh"        "$(have gh && gh --version | head -1 || echo 'MISSING (optional)')"
have gh && line "gh auth" "$(gh auth status 2>&1 | grep -m1 -E 'Logged in|not logged' || echo unknown)"
line "cloudflared" "$(have cloudflared && cloudflared --version 2>&1 | head -1 || echo 'MISSING (needed in Phase 4/7)')"
line "ffmpeg"    "$(have ffmpeg && ffmpeg -version | head -1 | cut -c1-40 || echo 'MISSING (optional)')"
line "docker"    "$(have docker && docker --version || echo 'MISSING (optional, Phase 7)')"
line "node"      "$(have node && node --version || echo 'MISSING (optional)')"
line "claude"    "$(have claude && claude --version 2>&1 | head -1 || echo MISSING)"
line "Proxy env" "${HTTPS_PROXY:-${https_proxy:-none}}"
[ -d ~/callbuddy ] && line "~/callbuddy" "exists" || line "~/callbuddy" "not created yet"
[ -f ~/callbuddy/.env ] && line ".env" "exists (contents not shown)" || line ".env" "not created yet"
echo "=== done ==="
