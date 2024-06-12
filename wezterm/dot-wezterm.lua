-- Pull in the wezterm API
local wezterm = require("wezterm")

-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices

-- For example, changing the color scheme:
config.color_scheme = "Catppuccin Mocha"
config.font = wezterm.font("SauceCodePro Nerd Font")
config.font_size = 15
config.initial_cols = 144
config.initial_rows = 44

-- and finally, return the configuration to wezterm
return config
