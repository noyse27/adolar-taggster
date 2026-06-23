# TagMeGently — Project Notes

## Building the EXE

Always use these hidden imports when building with PyInstaller, otherwise mutagen won't be included:

```
pyinstaller --onefile --windowed --name TagMeGently \
  --hidden-import mutagen \
  --hidden-import mutagen.mp3 \
  --hidden-import mutagen.id3 \
  --hidden-import mutagen.id3._util \
  tagger.py
```

## Release checklist

1. Bump version in `_open_about()` in tagger.py
2. Update CHANGELOG in README.md
3. `git add tagger.py README.md && git commit -m "vX.Y ..."`
4. `git push`
5. Build EXE (see above)
6. `git tag -a vX.Y -m "TagMeGently vX.Y" && git push origin vX.Y`
7. `gh release create vX.Y dist/TagMeGently.exe --title "..." --notes "..."`
