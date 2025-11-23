markdown
# 🍌 Banana Pro Studio (Gemini Image Tool)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Gradio](https://img.shields.io/badge/UI-Gradio-orange.svg)](https://gradio.app/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[中文文档](README.md) | [English](README_en.md)

**Banana Pro Studio** is a robust, localized AI image processing workbench built with Python and Gradio. It leverages the powerful visual capabilities of Google's Gemini models (Nano Banana / Flash / Pro) to provide a seamless experience for image generation, editing, and management.

More than just a script, this is a full-featured desktop web application featuring dark mode, multi-language support, asynchronous background processing, and comprehensive history management.

---

## ✨ Key Features

* **🤖 Powerful Model Support**: Seamless integration with Google Gemini 2.5 Flash Image and Gemini 3.0 Pro Image Preview models.
* **📂 Local Asset Management**: Built-in file browser to navigate local directories, supporting drag-and-drop and click-to-select.
* **⚡ Asynchronous Processing**: Tasks run in background threads. Supports session recovery—closing the tab won't stop the generation.
* **🎨 Modern UI/UX**:
    * **Dark/Light Mode** toggle.
    * **Responsive Layout**: Separated Assets view and Workbench view.
    * **Real-time Logging**: Monitor execution status directly in the UI.
* **💾 Persistence**:
    * SQLite-based auto-save for API keys, configurations, and prompt history.
    * Auto-archiving of generated results.
* **🌍 Internationalization (i18n)**: Native support for English and Chinese interfaces.
* **📦 Standalone Deployment**: Can be packaged into a single Windows `.exe` file.

---

## 🛠️ Installation & Launch

### Prerequisites
* Python 3.12 or 3.13 (Recommended)
* Windows / Linux / macOS

### 1. Clone the Repository

```bash
git clone [https://github.com/Joycai/Gemini-Image-Tool.git](https://github.com/Joycai/Gemini-Image-Tool.git)
cd Gemini-Image-Tool
```

### 2. Install Dependencies

It is recommended to use a virtual environment:

```Bash
python -m venv .venv
# Activate on Windows:
.\.venv\Scripts\activate
# Activate on Linux/Mac:
source .venv/bin/activate
```

Install core libraries:

```Bash
pip install gradio requests pillow google-genai pyinstaller
```

### 3. Launch the App

```Bash
python app.py
```
The browser will automatically open http://127.0.0.1:7860.

## 🔑 Configuration

After the first launch, click the "⚙️ Settings" button in the top toolbar:

+ Google API Key: Enter your Gemini API Key (Get it from Google AI Studio).
+ Auto Save Path: Set the directory where generated images will be saved. 
+ Language: Switch interface language (English/Chinese). Click "♻️ Restart App" to apply changes.

## 📦 Build Executable (EXE)

This project relies on several complex libraries (Gradio, Uvicorn, etc.). To ensure the packed `.exe` runs correctly on machines without Python, you must use the following specific command.

**Build Command**

```PowerShell
pyinstaller --noconsole --onefile --name="BananaProStudio" --add-data "lang;lang" --collect-all safehttpx --collect-all gradio_client --collect-all groovy --collect-all gradio app.py
```
Arguments Explanation
+ --noconsole: Hides the command line window (Remove this for debugging if the app crashes).
+ --onefile: Bundles everything into a single .exe file.
+ --add-data "lang;lang": [Crucial] Bundles the local translation files into the executable.
+ --collect-all ...: [Crucial] Forces PyInstaller to collect all metadata and version files for gradio and its sub-dependencies (safehttpx, groovy), preventing FileNotFoundError at runtime.

Once finished, the executable will be found in the dist/ folder.

## 🤝 Contribution

Issues and Pull Requests are welcome! Please feel free to report bugs or suggest new features.

## 📄 License
This project is licensed under the MIT License. See the LICENSE file for details.