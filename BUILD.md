# Building Gemini Image Tool (v0.2.3)

This guide provides instructions on how to build the Gemini Image Tool as a standalone application for Windows, macOS, and Linux using Flet and `uv`.

## Prerequisites

Before you begin, ensure you have the following installed:

1.  **Python 3.12**: The project specifically requires Python 3.12.x.
2.  **uv**: An extremely fast Python package and project manager.
3.  **Flutter SDK**: Flet requires the Flutter SDK to build desktop applications.
4.  **Platform-Specific Build Tools**:
    *   **Windows**: Visual Studio 2022 with "Desktop development with C++" workload.
    *   **macOS**: Xcode and Command Line Tools.
    *   **Linux**: `pkg-config`, `libgtk-3-dev`, `liblzma-dev`, `libstdc++-12-dev`.

## Setup with `uv`

We recommend using `uv` for managing the project environment and dependencies.

### 1. Install `uv`
If you haven't installed `uv` yet, follow the instructions for your platform:

*   **Windows (PowerShell)**:
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
*   **macOS / Linux**:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

### 2. Initialize Virtual Environment
From the project root, create a virtual environment and install dependencies:

```bash
# Create a venv with Python 3.12
uv venv --python 3.12

# Activate the environment
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install all dependencies from pyproject.toml
uv sync
```

## Build Commands

Once your environment is set up and activated, run the following commands to build for your target platform.

### Windows
```console
flet build windows --exclude .github .venv .git build gapp inno_scripts tests app.py .gitignore BUILD.md requirements.txt uv.lock
```

### macOS
```console
flet build macos --exclude .github .venv .git build gapp inno_scripts tests app.py .gitignore BUILD.md requirements.txt uv.lock
```

### Linux
```console
flet build linux --exclude .github .venv .git build gapp inno_scripts tests app.py .gitignore BUILD.md requirements.txt uv.lock
```

### Command Breakdown:
*   `flet build <platform>`: Tells Flet to compile the project for the specified platform.
*   `--exclude ...`: This flag ensures that temporary files, local databases, IDE configurations, and other unnecessary folders are not included in the final distribution package.

## Application Metadata

The build process uses the following configuration from `pyproject.toml`:
*   **Product Name**: Gemini-Image-Tool
*   **Version**: 0.2.3
*   **Company**: Joycai
*   **Main Module**: `flet_app`

## Output Location

Once the build process completes, you can find the executable and necessary runtime files in the `build/<platform>` directory.

## Troubleshooting

*   **Python Version**: Ensure you are using **Python 3.12**, as specified in the project configuration.
*   **Missing Build Tools**: Ensure the platform-specific compilers (Visual Studio, Xcode, or GCC/GTK devs) are correctly installed.
*   **Flutter Path**: If Flet cannot find Flutter, ensure the Flutter `bin` directory is added to your system's `PATH` environment variable.
