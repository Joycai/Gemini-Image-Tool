# Gemini Image Tool User Guide

Welcome to the Gemini Image Tool! This application leverages Google's GenAI to provide powerful image processing and chat capabilities. This guide will help you get started, from installation to using the various features.

## Table of Contents

1.  [Installation & Setup](#installation--setup)
2.  [Getting a Google GenAI API Key](#getting-a-google-genai-api-key)
3.  [Application Overview](#application-overview)
4.  [Features](#features)
    *   [Single Edit](#single-edit)
    *   [Chat](#chat)
    *   [Prompt Manager](#prompt-manager)
    *   [Prompt History](#prompt-history)
    *   [History](#history)
    *   [Queue](#queue)
    *   [Refine Manager](#refine-manager)
    *   [Settings](#settings)
5.  [Troubleshooting](#troubleshooting)

---

## Installation & Setup

### Prerequisites

*   **Python 3.12 or higher**: Ensure you have Python installed on your system. You can download it from [python.org](https://www.python.org/).

### Installation Steps

1.  **Clone or Download the Repository**:
    If you haven't already, download the project files to your local machine.

2.  **Install Dependencies**:
    Open a terminal or command prompt in the project's root directory (where `pyproject.toml` is located) and run the following command to install the required Python packages:

    ```bash
    pip install -r requirements.txt
    ```
    *Note: If you are using `uv` or another package manager, follow their specific instructions for installing dependencies from `pyproject.toml`.*

3.  **Run the Application**:
    Start the application by running the `flet_app.py` script:

    ```bash
    python flet_app.py
    ```

---

## Getting a Google GenAI API Key

To use this application, you need an API key from Google AI Studio.

1.  Go to [Google AI Studio](https://aistudio.google.com/).
2.  Sign in with your Google account.
3.  Click on **"Get API key"** (usually on the top left or in the settings).
4.  Click **"Create API key"**.
5.  Copy the generated key string. You will need to enter this in the application settings.

---

## Application Overview

Upon launching the application, you will see a main window with several tabs at the top. The application supports both Light and Dark themes, which can be toggled using the icon in the top-right corner.

## Features

### Settings
**First Step:** Before using any features, go to the **Settings** tab.

*   **General API Settings**:
    *   **API Key**: Paste your Google GenAI API key here. This is required for all AI operations.
*   **Refine Agent Settings**:
    *   **Refine Agent API Key**: (Optional) If you use a separate key for prompt refinement.
    *   **Refine Agent Model**: Select the model used for refining prompts (e.g., `gemini-2.0-flash`).
*   **Output Settings**:
    *   **File Prefix**: Set a prefix for generated filenames (default: `gemini_gen`).
    *   **Save Path**: Choose where generated images will be saved.
    *   **Max Prompt History**: Limit the number of saved prompt history entries.
*   **Language**: Switch between English and Chinese.
*   **Data Management**: Import or Export application data (settings, history, etc.) for backup.
*   **Application Management**: Clear cache or reset all data.

**Remember to click the "Save" button after making changes.**

### Single Edit
This is the main workspace for image generation and editing.

*   **Input**: Enter your prompt describing the image you want to generate or edit.
*   **Image Upload**: You can upload reference images to guide the generation.
*   **Generate**: Click the action button to send your request to Gemini.
*   **Result**: The generated image will appear in the view area. You can download it or use it for further edits.

### Chat
Interact with Gemini in a conversational format.

*   **Text & Images**: You can send both text messages and images to the model.
*   **Context**: The chat maintains a session context, allowing for follow-up questions and refinements.

### Prompt Manager
Manage and organize your frequently used prompts.

*   **Create**: Add new prompts with titles and descriptions.
*   **Edit/Delete**: Modify or remove existing prompts.
*   **Use**: Quickly insert saved prompts into your current workflow.

### Prompt History
View a log of your past prompts. This is useful for revisiting successful generations or analyzing past attempts.

### History
A gallery of your generated images.

*   **View**: Browse through images you've created.
*   **Manage**: Open the file location or delete unwanted images.

### Queue
Monitor the status of background tasks. If you have multiple generations running, you can see their progress here.

### Refine Manager
Configure and manage the "Refine Agent," which helps improve your prompts for better results.

---

## Troubleshooting

*   **API Key Errors**: Ensure you have copied the key correctly and that your Google Cloud project has the necessary quotas.
*   **Installation Issues**: Make sure you are using Python 3.12+ and have installed all requirements.
*   **Application Not Starting**: Check the console output for any error messages.

For further assistance, please refer to the project repository or contact the developer.
