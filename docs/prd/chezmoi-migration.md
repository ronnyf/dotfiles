---
version: 1.1.0
metadata:
  reference-process: v1.5.0
---

# PRD: Migrate dotfiles management from GNU stow to chezmoi

## Problem Statement

Config files are deployed via symlinks from a central git repo. Because symlinks write
through bidirectionally, any edit on any machine — whether deliberate or caused by an
installer appending to a file — flows straight into that machine's local repo clone.
Over time this produces dirty working trees on machines the developer hasn't touched in
days, merge conflicts when pushing, and accumulated divergence that requires manual
resolution to keep three Macs in sync.

Setting up a new Mac compounds the problem: the repo must be cloned, any pre-existing
files that would conflict with symlinks must be deleted by hand, every package must be
re-stowed in the right order, and separate setup scripts (Homebrew, macOS defaults) must
be remembered and run independently. There is no single command that results in a fully
configured machine.

A secondary pain point: agent skill files are stowed into tool-specific paths. When a new
agent tool is adopted, its skill path must be wired up and re-stowed. Skills are not
shared — each tool requires its own deployed copy.

## Desired Outcome

A developer working across three Macs experiences dotfiles as a clean, intentional sync
loop: make a change on one machine, commit and push, pull and apply on the others, with
no accidental state accumulation in the repo. Setting up a freshly imaged Mac or Linux
desktop is a two-command operation. Agent skills live in one canonical location and all
agent tools read from it automatically.

## Success Criteria

1. A single command on any existing machine pulls the latest config and applies it with
   no manual file editing required.
2. A freshly imaged Mac or Linux desktop (CachyOS/Arch) reaches a fully configured state
   — all platform-appropriate package manager tools installed, all config files applied,
   all agent skills deployed — via at most two commands after connecting to the internet.
3. Editing a config file and propagating the change to other machines requires no more
   than three deliberate steps (edit locally, commit, push/pull).
4. Dirty working trees caused by installers or live-file edits no longer occur. Only a
   deliberate developer action can alter the source state.
5. All supported agent tools read skills from the same canonical on-disk location
   without the developer maintaining separate copies.
6. Adding a new package manager dependency results in that dependency being installed
   automatically on the next sync on all machines.

## User Stories

As a developer working across three Macs and a few Linux (Arch based CachyOS) machines, 
I want config changes to sync without merge conflicts or manual cleanup, so that I do not 
spend time resolving dirty-tree divergence between machines.

As a developer setting up a new CachyOS or Arch Linux desktop, I want all tools and
config deployed in a single command, so that I do not need a separate setup process for
Linux machines.

As a developer setting up a new Mac, I want all tools and config deployed in a single
command, so that I do not need to remember or rediscover a multi-step bootstrap sequence.

As a user of multiple agent tools, I want my agent skills to be shared from a single
canonical location, so that adding or updating a skill is one operation regardless of how
many tools consume it.

As a developer who uses third-party agent skill repositories, I want those repos to be
installable automatically on a new machine, so that I do not need to remember to clone
them separately after bootstrapping.

As a developer who maintains a personal neovim config fork, I want that fork to be cloned
automatically on a new machine, so that neovim is fully configured without manual
intervention.

## Out of Scope

- Linux server configuration (managed separately via Ansible; CachyOS/Arch desktop machines are in scope).
- Neovim plugin management (owned by the plugin manager inside neovim, not dotfiles).
- Tmux plugin management (owned by TPM, not dotfiles).
- Zsh plugin management (owned by a dedicated zsh plugin manager, not dotfiles).
- Secret storage or credential management beyond file-permission control.
- A graphical interface for managing dotfiles.
- Automated upstream merging for personal forks or external skill repositories.

## Further Notes

The migration retains the existing dotfiles git repository and its remote. No git history
is lost and no new remote is created. The new tool is layered on top of the existing
repo structure; the old stow tooling is removed once the migration is complete.
