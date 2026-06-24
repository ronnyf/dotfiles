#!/usr/bin/env bash
[[ "$(uname -s)" == "Darwin" ]] || exit 0
set -e

# Keyboard: fast key repeat
defaults write NSGlobalDomain KeyRepeat -int 2
defaults write NSGlobalDomain InitialKeyRepeat -int 15

# Finder: show extensions, path bar, status bar
defaults write com.apple.finder ShowStatusBar -bool true
defaults write com.apple.finder ShowPathbar -bool true
defaults write NSGlobalDomain AppleShowAllExtensions -bool true

# Dock: auto-hide, remove delay
defaults write com.apple.dock autohide -bool true
defaults write com.apple.dock autohide-delay -float 0

# Screenshots: save to ~/Desktop
defaults write com.apple.screencapture location -string "${HOME}/Desktop"

killall Finder Dock 2>/dev/null || true
