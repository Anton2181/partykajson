# Distributing Partyka Solver Pro

## 1. Locating the Build

After running `python src/build.py`, the standalone application is generated in the **`dist/`** folder.

*   **Mac**: `dist/PartykaSolverPro.app` (This is a bundled folder)
*   **Windows**: `dist/PartykaSolverPro` (This is a folder containing the `.exe` and dependencies)

## 2. Running the App

### macOS
1.  Navigate to `dist/`.
2.  Double-click `PartykaSolverPro.app`.
    *   *Note: If macOS blocks it as "Unverified Developer", right-click > Open and confirm.*

### Windows
1.  Navigate to `dist/PartykaSolverPro/`.
2.  Double-click `PartykaSolverPro.exe`.
    *   *Do NOT move the .exe out of this folder. It needs the surrounding files to work.*

## 3. How to Distribute (Share)

### macOS
Right-click `PartykaSolverPro.app` and select **Compress "PartykaSolverPro"**. This creates a `.zip` file that you can email or upload to Google Drive/Dropbox. The recipient just needs to unzip it and run.

### Windows
Right-click the **entire** `PartykaSolverPro` folder inside `dist/` and select **Send to > Compressed (zipped) folder**. Send this zip file.
*   **Crucial**: Do not just send the `.exe`. The recipient needs the whole folder.

## 4. Cross-Platform Building

PyInstaller is **not** a cross-compiler.
*   To build for **Mac**, you must run `python src/build.py` on a **Mac**.
*   To build for **Windows**, you must run `python src/build.py` on a **Windows PC**.

The source code is identical. You just need to run the build script on the target OS.
