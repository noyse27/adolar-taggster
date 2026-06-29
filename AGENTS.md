# Adolar Taggster — Project Notes

## Building the EXE

Always use these hidden imports when building with PyInstaller, otherwise mutagen won't be included:

```
C:\Users\noyse\AppData\Local\Python\bin\python.exe -m PyInstaller --onefile --windowed --name AdolarTaggster --collect-all mutagen --collect-all PIL tagger.py
```

**Important:** Must use `C:\Users\noyse\AppData\Local\Python\bin\python.exe` explicitly — this is the Python installation where mutagen/PyQt6/Pillow are installed. The `python` command on PATH points to `C:\Python314\` which does NOT have these packages. Using the wrong Python produces "No module named 'mutagen'" in the EXE.

## Release checklist

1. Bump version in `_open_about()` in tagger.py
2. Update CHANGELOG in README.md
3. `git add tagger.py README.md && git commit -m "vX.Y ..."`
4. `git push`
5. Build EXE (see above)
6. `git tag -a vX.Y -m "Adolar Taggster vX.Y" && git push origin vX.Y`
7. `gh release create vX.Y dist/AdolarTaggster.exe --title "..." --notes "..."`
