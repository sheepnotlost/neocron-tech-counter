# Neocron Tech Counter

Counts the items in an open Neocron cabinet, including stack sizes, by reading the screen. It never clicks
and never reads game memory. It only moves the mouse over each filled slot so the game shows its tooltip.
`SPEC.md` is the source of truth.

## Download (no Python, no installs)
Download **`Neocron Tech Counter.exe`** from the top of this page (click it, then the download button) and run it. Tesseract OCR is built in, so there is nothing else to install. Your lists, settings and exports are saved next to the .exe, so keep it in its own folder.

Build it yourself: `python -m pip install pyinstaller`, install Tesseract (`winget install UB-Mannheim.TesseractOCR`), then `python tools/build_exe.py` (output in `dist/`).

## Install from source (instead of the .exe)
1. Python 3.14 and `python -m pip install -r requirements.txt`
2. Tesseract OCR: `winget install UB-Mannheim.TesseractOCR` (default path is fine)

## Use
```
python -m ntc
```
1. In game, open a cabinet and/or your inventory (F2). There is nothing to set up: the tool finds the windows
   itself, wherever they are and whatever HUD color you use.
2. Pick what to scan in the **Scan:** dropdown (all / cabinet / inventory) and what to record in the **Log:** dropdown
   (all items / techs only), then click **Scan** or press **Ctrl+Alt+S**.
   For each window it scrolls to the top, reads every slot (hovering each item for its name), scrolls down, and
   repeats until the bottom. Stop early with **Ctrl+Alt+X**, or just move the mouse yourself.
3. Each window is **added to the active list** as "Cabinet 1", "Inventory 1", ... and the list keeps a running
   total. Scanned the wrong thing? **Undo last scan**.
4. **Lists** (top of the window): New, Rename, Delete, and a selector to switch. Lists are saved in `lists.json`.
5. **Scans in this list**: double-click one to edit names/quantities, or use Rename / Delete scan / Add manual
   entry. Double-click an item in the totals to see which cabinets hold it. Corrections are remembered in
   `known_items.json`.
6. **Export** the active list: clipboard, CSV, CSV by cabinet, TXT or JSON. Every export lists which cabinet(s)
   hold each item.

## Notes
- If the game runs as administrator, run this tool as administrator too (Windows blocks input into elevated windows).
- The tool scrolls with the mouse wheel. If a window does not scroll and has items on its last row, the app warns you.
- A window covered by another window (for example the Options window) is not found: close what covers it.
- The mouse is returned to where it was when the scan finishes.
- With **Log: techs only** the scan reads each slot's short label first (COMP, HULL, ATP, CORE, FRAM, TECH) and does not hover items that are clearly not techs, so inventory scans are much faster.
- The windows use a Neocron-style frame (cut corners, own title bar with minimise and close, drag the title bar, resize at the edges or the bottom-right grip) in the game's font and green gem colours.

## Other commands
`python -m ntc scan [all|cabinet|inventory]` (headless scan), `windows [screenshot.png]` (show what is detected), `capture` (save screenshots), `python -m pytest` (about 3 minutes).


## Data
`data/tech_sets.json` / `data/tech_sets.md`: which parts complete each rare (from rares.techhaven.org, 86 items). Used by the Sets window.

## Sets
The **Sets...** button shows which rares your active list can complete: green = complete, yellow = missing one part. Double-click a row to see each part and which cabinet holds it. Filter, search, Copy or Save CSV.
