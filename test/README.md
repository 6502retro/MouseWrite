# Testing in the apple2js emulator

```sh
git clone --recurse-submodules https://github.com/whscullin/apple2js.git
cd apple2js && git apply /path/to/MouseWrite/test/apple2js.patch
npm ci --ignore-scripts
(cd submodules/cpu6502 && npm install --ignore-scripts && npx tsc --build)
npm install --ignore-scripts --no-save ./submodules/cpu6502 ./submodules/apple2shader
npx webpack --mode=production
python3 -m http.server 8765 &          # serve the emulator (put disk images in img/)
SHOTS=/tmp node /path/to/MouseWrite/test/harness.js 9301 http://localhost:8765/img/A2DeskTop.hdv
```

The patch fixes the emulator's mouse-card ROM stub (see [docs/INTERNALS.md](../docs/INTERNALS.md#the-emulator)) and exposes the emulator objects as `window.__a2`.

Drive the harness by POSTing a list of commands:

```sh
curl -s -X POST localhost:9301 -d '{"cmds":[["wait",40],["move",514,50],["down"],["up"],["down"],["up"],["wait",6],["text"],["shot","desktop"]]}'
```

| Command | Does |
|---|---|
| `["wait", s]` | wait s seconds |
| `["move", x, y]` | move the mouse (x 0-559, y 0-383) |
| `["down"]`, `["up"]` | mouse button |
| `["key", "text"]`, `["keycode", n]` | type, `\n` = Return |
| `["oa", true/false]`, `["sa", …]` | hold Open-Apple / Solid-Apple |
| `["text"]` | the 80-column text screen, read from memory |
| `["waittext", regex, s]` | wait until the screen matches |
| `["shot", name]` | screenshot to `$SHOTS/name.png` |
| `["reload", url]`, `["hdd", drive, url]`, `["floppy", drive, url]` | change disks |
| `["save", drive, file]` | write the hard disk back to a file |
| `["eval", js]`, `["peek", addr, n]` | inspect the emulator |

Apple II DeskTop 1.5 positions used in testing (after booting the `A2.DESKTOP` volume): volume icon `514,50`, the `MOUSEWRITE` folder (second icon of the third row) `114,234`, `MW.SYSTEM` inside it `80,124`. MouseWrite menus: *MouseWrite* `30,8`, *File* `108,8`. Menu row *n* is at `y = 16n + 8`.
