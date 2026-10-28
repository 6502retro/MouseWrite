# Your original disks go here

Put images of your own MouseWrite disks in this folder, then run `python3 build.py`. Disks are recognised by their contents, so file names don't matter.

| Disk | Needed? | Used for |
|---|---|---|
| **MouseWrite 2.6.8b**, 800K (`/MOUSEWRITE`, `.2mg` or `.po`) | required | program, accessories, fonts, speller, samples, tutorial |
| 5.25" **SPELLER** disk (`/SPELLER`) | optional | its personal-dictionary words are merged in |
| **Art Pack** 3.0, 3.1, 3.2, 4 (`/ART3`, `/ARTPAK3.1`, `/ARTPAK3.2`, `/ART4`) | optional | copied to `MOUSEWRITE/ART.PACKS/` |
| **MouseWrite 1.5.7** (`/MOUSEWRITE`) | optional | installed as its own `MW.V1.5.7` folder |

`.2mg`, `.po`, `.hdv`, `.dsk` and `.do` all work. You can also pass paths directly: `python3 build.py DISK1 DISK2 …`. Other disks, such as the 2.6.8 floppy set, are listed as "not used" and skipped.

The build was made against the 2.6.8b disk whose `MW.SYSTEM` has SHA-1 `5daa80bf0e62e197455731985b1cbb4337c44d80`. Every file it changes is checked, so a different release stops with an error rather than producing a broken disk.

Nothing in this folder is committed to git (see `.gitignore`), because these are copyrighted disks.
