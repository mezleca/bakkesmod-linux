# BakkesMod Linux

BakkesMod for linux.
This is an updated and cleaner version of [mezleca/BakkesLinux](https://github.com/mezleca/BakkesLinux).

## What does this do?

This allows you to use **BakkesMod** on Linux **without relying on the official Windows installer inside each Wine/Proton prefix**.

Instead of fighting with multiple prefixes, broken installers, or duplicated files, this tool:

- Downloads and manages **all required BakkesMod files once**
- Copies **only what is needed** into the target Wine/Proton prefix.
- Uses symlink for plugins / cfgs, meaning even if you uninstall the prefix, the config files should remain intact.
- Uses a **minimal C++ injector** to inject the bakkesmod on the wine process.
- Uses Python only for **update checks, file management, etc...**

## Todo
- [ ] create workflow to compile the c++ injector
- [ ] download the c++ injector from gh releases instead of using the manually copied one
- [ ] test on other launchers (steam, lutris)

## Requirements

- Python 3.8+
- Rocket League

## Installation

### pipx (recommended)

```bash
# install bakkesmod 
pipx install git+https://github.com/mezleca/bakkesmod-linux.git

# if you want to create a .desktop file for BakkesMod, run:
bakkesmod --create-desktop
```

### From source

```bash
git clone https://github.com/mezleca/bakkesmod-linux.git
cd bakkesmod-linux
pip install -e .
```
