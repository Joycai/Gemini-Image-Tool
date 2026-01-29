# 🍌 Banana Pro Studio (Gemini Image Tool)

[![Version](https://img.shields.io/badge/Version-0.3.0-brightgreen.svg)](pyproject.toml)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Flet](https://img.shields.io/badge/Flet-0.80.0-blueviolet.svg)](https://flet.dev)
[![Google GenAI](https://img.shields.io/badge/Google%20GenAI-1.60.0-4285F4.svg)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Banana Pro Studio** is a local AI image processing workbench built with Python and Flet. It leverages the powerful vision capabilities of the Google Gemini model family to provide users with a seamless experience for image generation, editing, and management.

This is more than just a simple script; it's a full-featured, desktop-grade application that supports dark mode, a multilingual interface, asynchronous background task processing, and comprehensive history management.

---

## ✨ Key Features

*   **🤖 Powerful Model Support**: Seamlessly integrates with Google's `gemini-2.5-flash-image` and `gemini-3-pro-image-preview` models, with support for custom model IDs.
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
    *   Includes Flet packaging commands to bundle the application into a single executable file for easy distribution.

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
python flet_app.py
```
After launching, a native desktop application window will open.

---

## 📦 Packaging as an Executable

You can package the application into a standalone desktop application.

### Packaging the Flet App
Flet comes with a simple, built-in packaging tool.
```bash
# Run the packaging command
flet pack flet_app.py
```
The final executable will be located in the `dist/` directory.

### Build native Application
**Windows**
```bash
flet build windows
```
---

## 🧪 Running Tests

This project includes a suite of unit tests to ensure the stability and correctness of its core features. The test cases are located in the `tests/` directory.

To run all tests, execute the following command from the project's root directory:

```bash
python -m unittest discover tests
```
If all tests pass, you will see an "OK" message.

---

## 📖 User Guide

### 1. Initial Setup
1.  After launching the app, click the **"⚙️ Settings"** tab at the top.
2.  **Google API Key**: Enter your Gemini API Key (you can get one from [Google AI Studio](https://aistudio.google.com/app/apikey)).
3.  **Auto Save Path**: Set a directory where your generated images will be permanently saved. The history feature will be disabled if this is left empty.
4.  **Language**: Choose your preferred interface language.
5.  Click **"💾 Save Config"**.

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

## 🤝 Contributing

Issues and Pull Requests are welcome! If you find a bug or have a feature request, please don't hesitate to open an issue.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
