# Adolar Taggster — Project Notes

## Building the EXE

```
C:\Users\noyse\AppData\Local\Python\bin\python.exe -m PyInstaller --onefile --windowed --name AdolarTaggster --collect-all mutagen --collect-all PIL --collect-all PyQt6 --hidden-import PyQt6.sip --add-binary "C:\Users\noyse\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\PyQt6\sip.cp314-win_amd64.pyd;PyQt6" tagger.py
```

**Important:** Must use `C:\Users\noyse\AppData\Local\Python\bin\python.exe` explicitly — this is the Python installation where mutagen/PyQt6/Pillow are installed. The `python` command on PATH points to `C:\Python314\` which does NOT have these packages. Using the wrong Python produces "No module named 'mutagen'" in the EXE.

**`--collect-all mutagen --collect-all PIL`** — without these, mutagen/Pillow are silently missing from the build.

**`--collect-all PyQt6 --hidden-import PyQt6.sip --add-binary ".../sip.cp314-win_amd64.pyd;PyQt6"`** — without these, the EXE crashes instantly on launch with `ModuleNotFoundError: No module named 'PyQt6.sip'`. This appeared starting with this Python 3.14 + PyInstaller 6.22.2 combo: PyInstaller's own `hook-PyQt6.py` declares `PyQt6.sip` as a hidden import, but its module-graph analysis still fails to resolve the compiled `sip.cp314-win_amd64.pyd` extension, so it has to be forced in explicitly via `--add-binary`. If the Python version changes, find the current filename with:
`Get-ChildItem "C:\Users\noyse\AppData\Local\Python\pythoncore-*\Lib\site-packages\PyQt6\sip.*.pyd"`
and update the `--add-binary` path accordingly. **Always launch the freshly built EXE once and confirm a window actually opens before treating a build as done** — a "Build complete!" message from PyInstaller does not mean the EXE runs; this exact bug produced a "successful" build that crashed immediately every time.

## Release checklist

1. Bump version in `_open_about()` in tagger.py
2. Update CHANGELOG in README.md
3. `git add tagger.py README.md && git commit -m "vX.Y ..."`
4. `git push`
5. Build EXE (see above)
6. `git tag -a vX.Y -m "Adolar Taggster vX.Y" && git push origin vX.Y`
7. `gh release create vX.Y dist/AdolarTaggster.exe --title "..." --notes "..."`
