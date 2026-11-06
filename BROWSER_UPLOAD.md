# Upload through the GitHub website

GitHub accepts up to 100 files in one browser upload, with a 25 MiB limit per file.
The browser-upload download divides this repository into six batches, each with
at most 95 files. See the [GitHub upload instructions](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).

## Upload the batches

1. Extract `adf-sentinel-browser-upload-batches.zip` on your computer.
2. Open your GitHub repository's main page, at the repository root.
3. Choose **Add file → Upload files**.
4. Open `batch-01` on your computer. Select its **contents** and drag those files
   and folders into the GitHub upload area. Keep the existing folder structure.
5. Commit that upload.
6. Repeat for `batch-02` through `batch-06`, starting at the repository root each
   time and committing each batch before starting the next.

Upload one batch at a time. The batch folder names are packaging labels and
should not become directories in the repository. Uploading the ZIP itself stores
an archive; extracting it first makes the source and README available normally.

Batch 1 contains the README, all README figures, the requirements example and
review workbench. Complete all six batches before running the full checks or
verifying `PACKAGE_MANIFEST.json`.

## Hidden files

Include `.gitignore` and `.env.example` from batch 1. If your file manager hides
them, show hidden files before selecting the batch contents: **Command + Shift +
period** on macOS, or **Ctrl + H** in common Linux file managers. Windows normally
shows these dot-prefixed filenames without a special setting.

## Verify the completed repository

After all batches are uploaded, download or clone the repository and run:

```bash
python tools/verify_release.py
```

The complete original ZIP and Git upload commands remain available as an
alternative; see the top-level README. Browser batches contain the same files
and bytes as the complete repository package.
