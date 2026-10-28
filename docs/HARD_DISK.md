# MouseWrite 3.0 on a hard disk

## Why 2.6.8b didn't just work

MouseWrite has no copy protection, and its program files are found relative to the current ProDOS prefix, so the program itself starts from any folder. But it keeps three **full pathnames** in its preference files, all pointing at the original floppy names:

| Setting | Stored in | As shipped |
|---|---|---|
| Standard Document Location | `MW.GP` | `/MOUSEWRITE/SAMPLES/` |
| Standard Desk Accessory Location | `MW.GP` | `/MOUSEWRITE/ACCESSORY/` |
| Standard Speller Location | `MW.UI` | `/MOUSEWRITE/SPELLER/` |

From a hard-disk folder, *Desk Accessories* stops with **"The required Volume cannot be found – Please insert this volume: /MOUSEWRITE/ACCESSORY/"**. The Speller and the default Open/Save folder fail the same way. You *can* fix them by hand in *Startup Preferences → Disk*, but they break again whenever the folder moves.

## What 3.0 does

1. `build.py` presets the three paths to wherever it installs the folder.
2. Every time MouseWrite starts, the add-on in `MW.SYSTEM` checks each path. If the folder named can't be found **and** a folder of that name (`SAMPLES`, `ACCESSORY`, `SPELLER`) exists next to `MW.SYSTEM`, it rewrites the path and saves the preference file. Paths that work are never touched.

So a copied or moved `MOUSEWRITE` folder fixes itself the first time it runs. In testing, a copy moved to `/A2.DESKTOP/APPS/MW` with stale paths was fixed on first launch, and the Speller worked.

## Installing

* **With `--install-into`:** `python3 build.py --install-into A2DeskTop.hdv` writes `out/A2DeskTop.hdv` with the folder added. Boot it and open *MOUSEWRITE*.
* **By copying:** mount `out/MouseWrite_3.0_Folder.hdv` as a second drive in your emulator, or on a CFFA/BOSS card, and drag `MOUSEWRITE` onto your hard disk in Apple II DeskTop.

Then open the folder and double-click **MW.SYSTEM** (the first icon). Quit with *File → Quit* (it is greyed out while a document is open: close the document first). Quit returns you to DeskTop.

## Tips

* **Open/Save:** use option 3 (Open-Apple-3, *pathname*). It is pre-filled with the `MOUSEWRITE/SAMPLES/` folder, so just type a name or a sub-path. *Drive 1* and *Drive 2* mean the two floppy drives in slot 6. To point them at another slot, use *MouseWrite → Startup Preferences → Disk → Set Disk Drive Slot Number*.
* **Startup Preferences** is only available with no document open.
* **Desk Accessories** are under the *MouseWrite* menu. Type `BYE` in *Basic.System* to get back to MouseWrite. The title screen is not shown again when you do.
* **Custom fonts:** open the `SAMPLES/CF.GLOSS` glossary, press Control-G then `a`, `c` or `e` (Apple, C.Itoh, Epson). A font marker and the folder path are inserted; type the font name (e.g. `GOTHIC.IW`). `CF.GLOSS` is the one file that doesn't fix itself if the folder moves. Edit its three lines (it's a text file) or type the path yourself.
* **Mouse tutorial:** double-click `MOUSE.TUTORIAL/STARTUP`. Choice 2 starts MouseWrite from the folder above it.
* **MouseWrite 1.5.7** (if you supplied its disk) is in `MW.V1.5.7`. It has no accessories or speller; open its sample files with the pathname option.

## Known limits

* **Art Packs:** the Art Pack disks contain 576-dot printer graphics and two large display fonts (`HELVETICA`, `SERIF`). Nothing in MouseWrite 2.6.8b or its accessories reads them, so they're copied to `ART.PACKS/` but can't be used from MouseWrite as-is. The program that used them wasn't among the disks this was built from.
* **Expanded Desktop** (more than one open document) needs extra memory beyond 128K, as before.
* **Communications** needs a serial card. In the emulator, which has none, it closes straight away, as it does on the original floppy.

## Troubleshooting

* **"The required Volume cannot be found"** after moving the folder: make sure `SAMPLES`, `ACCESSORY` and `SPELLER` are still inside the `MOUSEWRITE` folder, next to `MW.SYSTEM`. Then quit and start MouseWrite again.
* **Launched by a program selector that doesn't set the prefix:** MouseWrite needs the ProDOS prefix to be its own folder, as it always has. Apple II DeskTop, Bitsy Bye and BASIC.SYSTEM's `-MW.SYSTEM` (after `PREFIX`) all do this.
* **No title picture:** `MW.SPLASH` must be in the same folder as `MW.SYSTEM`. Without it MouseWrite simply starts without the picture.
