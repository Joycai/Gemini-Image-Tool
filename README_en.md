# 🍌 Banana Pro Studio (Gemini Image Tool)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Gradio](https://img.shields.io/badge/UI-Gradio-orange.svg)](https://gradio.app/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Banana Pro Studio** is a local AI image processing workbench built with Python and Gradio. It leverages the powerful vision capabilities of the Google Gemini model family to provide users with a seamless experience for image generation, editing, and management.

This is more than just a simple script; it's a full-featured, desktop-grade web application that supports dark mode, a multilingual interface, asynchronous background task processing, and comprehensive history management.

---

## ✨ Key Features

*   **🤖 Powerful Model Support**: Seamlessly integrates with Google's `gemini-1.5-flash` and `gemini-1.5-pro` models, with support for custom model IDs.
*   **🎨 Flexible Generation Control**:
    *   Supports **Text-to-Image** and **Image-to-Image** generation (with up to 5 reference images).
    *   Customizable **aspect ratios** and **resolutions** for generated images.
    *   Includes an "Auto" aspect ratio option, allowing the model to determine the best fit.
*   **📂 Local Asset Management**:
    *   Built-in file browser to directly access and use materials from your local folders.
    *   Supports drag-and-drop or click-to-upload for images.
*   **⚡ Asynchronous Task Handling**:
    *   Generation tasks are processed in a background thread, preventing the UI from freezing.
    *   Results are automatically displayed and added to the history upon completion.
*   **💾 Data Persistence & Management**:
    *   **Prompt Management**: Save, load, and delete frequently used prompts.
    *   **Output History**: Automatically archives all generated images, with options to preview, download, and delete.
    *   **Auto-saved Configuration**: Your API key, save paths, and other settings are stored locally using SQLite, eliminating the need for repeated setup.
*   **🌐 Modern UI & UX**:
    *   One-click switching between **Dark and Light modes**.
    *   Interface available in both **Chinese** and **English** (requires a restart to apply).
    *   Real-time execution log for monitoring the application's status.
*   **📦 Cross-Platform & Packagable**:
    *   Runs on Windows, macOS, and Linux.
    *   Includes PyInstaller commands to bundle the application into a single executable file for easy distribution.

---

## 🛠️ Installation and Usage

### Prerequisites
*   Python 3.12+
*   Git

### 1. Clone the Repository
```bash
git clone https://github.com/Joycai/Gemini-Image-Tool.git
cd Gemini-Image-Tool
```

### 2. Create a Virtual Environment and Install Dependencies
Using a virtual environment is recommended to avoid package conflicts.

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
python app.py
```
After launching, the application will automatically open in your default browser at `http://127.0.0.1:7860`.

---

## 📖 User Guide

### 1. Initial Setup
1.  After launching the app, click the **"⚙️ Settings"** tab at the top.
2.  **Google API Key**: Enter your Gemini API Key (you can get one from [Google AI Studio](https://aistudio.google.com/app/apikey)).
3.  **Auto Save Path**: Set a directory where your generated images will be permanently saved. The history feature will be disabled if this is left empty.
4.  **Language**: Choose your preferred interface language.
5.  Click **"💾 Save Config"**. Language changes require a system restart by clicking the **"♻️ Restart System"** button at the top of the app.

### 2. Basic Workflow
1.  **Select Assets**:
    *   In the **"Local Folder"** tab, click **"📂 Browse"** to select a folder containing your source images. They will be displayed in the gallery below.
    *   Alternatively, switch to the **"Upload"** tab to drag and drop or click to upload temporary images.
2.  **Add Reference Images**:
    *   Click on any image in the asset galleries, then click the **"➡️ Add to Selected"** button. The image will appear in the "Selected Images" area at the top of the control panel.
    *   You can select up to 5 images as references for generation.
3.  **Write a Prompt**: In the "Prompt" text box on the right, describe the image you want to create in detail.
4.  **Adjust Parameters**: Choose the model, aspect ratio, and resolution as needed.
5.  **Start Generating**: Click the **"🚀 Generate / Edit"** button. The task will run in the background, and you can monitor its progress in the "Execution Log".
6.  **View Results**:
    *   Upon success, the new image will appear in the "Preview" area on the bottom right.
    *   It will also be automatically added to the "Output History" gallery on the bottom left.

---

## 📦 Packaging as an Executable

If you want to run this application on a computer without a Python environment, you can package it using PyInstaller.

```bash
# Make sure PyInstaller is installed: pip install pyinstaller

# Run the packaging command (recommended from the project root)
pyinstaller app.py --noconsole --onefile --name "BananaProStudio" \
--add-data "assets;assets" \
--add-data "lang;lang" \
--collect-all "gradio_client" \
--collect-all "quickjs" \
--collect-all "uvicorn"
```

**Command Breakdown**:
*   `--noconsole`: (Windows only) Prevents the command-line window from appearing when the app runs.
*   `--onefile`: Bundles everything into a single executable file.
*   `--add-data "assets;assets"`: **[Crucial]** Packages the `assets` folder containing CSS and JS files.
*   `--add-data "lang;lang"`: **[Crucial]** Packages the `lang` folder containing language files.
*   `--collect-all`: **[Crucial]** Forces PyInstaller to include all necessary dynamic libraries and dependencies for Gradio, preventing "File Not Found" errors at runtime.

The final executable will be located in the `dist/` directory.

---

## 🤝 Contributing

Issues and Pull Requests are welcome! If you find a bug or have a feature request, please don't hesitate to open an issue.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
