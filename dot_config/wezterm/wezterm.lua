-- Pull in the wezterm API
local wezterm = require("wezterm")

-- This will hold the configuration.
local config = {}
config.color_scheme = "Catppuccin Mocha"
config.font = wezterm.font("SauceCodePro Nerd Font")
config.font_size = 15
config.initial_cols = 134
config.initial_rows = 34

-- and finally, return the configuration to wezterm
return config
