# TeamMARS-PID-tuner(DRONE)

TeamMARS edition of [ArduPilot Methodic Configurator](https://github.com/ArduPilot/MethodicConfigurator) v5.1.1
(GPL-3.0-or-later). Same workflow, same backend, same safety checks — new name and a liquid-glass UI.

Git branch: `teammars-glass` (upstream tag `v5.1.1` is the base).

## Where things are

| What | File |
|---|---|
| App name, window class | `ardupilot_methodic_configurator/branding.py` |
| Glass theme + palette | `ardupilot_methodic_configurator/frontend_tkinter_glass_theme.py` |
| App icon | `ardupilot_methodic_configurator/images/TeamMARS_icon.png` (regenerate: `teammars/make_icon.py`) |
| Widget gallery (preview the theme without the app) | `.venv/bin/python teammars/theme_gallery.py` |
| Launcher | `~/.local/share/applications/teammars-pid-tuner.desktop` |

## Palette

| Role | Colour |
|---|---|
| Bottle green (primary: buttons, chips, headings, selection) | `#006A4E` |
| Bone (surface) | `#E3DAC9` |
| Frosted glass (fields, lists) | `#FBF8F2` |
| Vermilion (hint: focus rims, selected-tab underline, progress) | `#E34234` |
| Text | `#1D2A24` |

Change a colour in `frontend_tkinter_glass_theme.py` and restart the app — the install is editable, no rebuild.

## Rules kept on purpose

- **Safety colours unchanged in meaning**: light blue = default value, orange-red = below limit, red = above limit,
  yellow = calibration param, purple = read-only. Fields stay colour-based so these always show.
- **No blur / transparency**: glass is drawn as small pre-rendered images, so the UI is as fast as before.
- **Backend untouched**: no change to MAVLink, parameter upload, file handling or configuration steps.
- **Credits kept**: the About box and file headers still credit the original authors (required by the GPL).

## Undo everything

```bash
cd ~/MethodicConfigurator && git stash -u   # puts the TeamMARS changes aside (bring back with: git stash pop)
```
