#!/usr/bin/env bash
[[ "$(uname -s)" == "Darwin" ]] || exit 0
set -e
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001
defaults write com.apple.dock expose-animation-duration -float 0.1
defaults write com.apple.dock autohide-time-modifier -float 0
