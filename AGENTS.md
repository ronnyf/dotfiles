# AGENTS.md

This file contains guidelines for working with this dotfiles repository.

## Architecture

This dotfiles repository uses GNU Stow for symlink management with a custom `stowy.sh` wrapper:

- Each directory represents a package to be stowed
- Each package directory contains a `target.stowy` file specifying the target path
- Payload files are named with `dot-` prefix (e.g., `dot-zshrc`, `dot-p10k.zsh`)
- Run `./stowy.sh` to install/update all packages
- Packages: `zshrc`, `zsh`, `zsh_custom`, `tmux`, `nvim`, `omz`, `omz_plugins`, `omz_themes`, `wezterm`, `ghostty`, `fd`, `iTerm2`, `xcode-themes`

## Package Structure

Each package directory follows this pattern:

```
package/
├── target.stowy      # Specifies STOWY_TARGET path
├── dot-file1         # Payload files (dot- prefix)
├── dot-file2
└── subdirectory/
    ├── dot-file3
    └── target.stowy  # Optional nested target
```

The `stowy.sh` script:
1. Finds all directories containing `target.stowy`
2. Reads `STOWY_TARGET` from each file
3. Creates target directory if needed
4. Runs `stow -t <target> -v <package> --dotfiles`

## Naming Conventions

- **Files**: snake_case with `.lua`, `.zsh`, `.conf` extensions
- **Dotfiles**: use `dot-` prefix (e.g., `dot-zshrc`)

## Key Configuration Files

- **Zsh**: `zshrc/dot-zshrc` (main config), `zsh/dot-p10k.zsh` (powerlevel10k)
- **Neovim**: `nvim/nvim/init.lua`, `nvim/nvim/lua/options.lua`
- **Tmux**: `tmux/tmux.conf`
- **Keymaps**: `nvim/nvim/lua/mappings.lua`

## Important Notes

- This is a dotfiles repository - changes affect user environment
- Test changes in a safe environment before committing
- Run `./stowy.sh` to install/update all symlinks after making changes
- Subdirectories (omz, omz_plugins, omz_themes, nvim/nvim) are opaque payloads managed by their respective tools
