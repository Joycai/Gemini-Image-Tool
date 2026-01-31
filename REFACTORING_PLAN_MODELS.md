# Refactoring Plan: Multi-Series Model Management and Unified API Layer

This document outlines the plan to refactor the application to support multiple model series (Google GenAI and OpenAI API) and unify the API calling logic.

## 1. Data Structure Refinement

### 1.1 Model Definition
Models will be stored in the database with the following attributes:
- `id`: Unique identifier (e.g., `gpt-4o`, `gemini-2.0-flash`).
- `series`: `google-genai` or `openai`.
- `type`: `chat` or `image`.
- `display_name`: (Optional) User-friendly name.

### 1.2 Database Changes
- Update `settings` or create a new `models` table to store the list of available models.
- Default models will be pre-populated.

## 2. Unified API Layer (Middle Layer)

Create `src/geminiapi/unified_client.py` to act as a bridge between the UI and low-level clients.

### 2.1 Responsibilities
- **Routing**: Determine which low-level client (`api_client.py` or `openai_client.py`) to call based on the model's `series`.
- **Abstraction**: Provide a consistent interface for the UI components:
    - `generate_image(model_id, prompt, images, ...)`
    - `chat_completions(model_id, messages, ...)`
    - `refine_prompt(model_id, prompt, ...)`
- **Response Normalization**: Convert different API responses into a standard format used by the Flet components.

## 3. Model Management Dialog

Refactor the dialog in `src/fletapp/component/flet_settings_page.py`.

### 3.1 Features
- **Series Selector**: Dropdown to choose between Google GenAI and OpenAI.
- **Model List**: Display models for the selected series with tags indicating their type (Chat/Image).
- **Add Model**: Form to input Model ID and select its type (Chat or Image).
- **Edit/Remove**: Actions for each model in the list.
- **Persistence**: Save the entire model configuration to the database.

## 4. UI Component Updates

### 4.1 `flet_single_edit_tab.py`
- Filter the model dropdown to only show models where `type == 'image'`.
- Call `unified_client.generate_image`.

### 4.2 `flet_chat_page.py`
- Filter the model dropdown to only show models where `type == 'chat'`.
- Call `unified_client.chat_completions`.

### 4.3 `flet_refine_manager_tab.py` & Refine Logic
- Use the unified client for prompt refinement.

## 5. Low-Level Client Updates

### 5.1 `src/geminiapi/openai_client.py`
- Implement `generate_image` (DALL-E support).
- Implement `chat_completions` (Standard OpenAI chat).

### 5.2 `src/geminiapi/api_client.py`
- Ensure it handles Google GenAI specific logic (already mostly done).

## 6. Implementation Steps

1.  **Step 1**: Update `database.py` to support the new model storage format.
2.  **Step 2**: Implement the `unified_client.py` middle layer.
3.  **Step 3**: Refactor `openai_client.py` to support chat and image generation.
4.  **Step 4**: Build the new Model Management Dialog in `flet_settings_page.py`.
5.  **Step 5**: Update `flet_single_edit_tab.py` and `flet_chat_page.py` to use the unified client and filtered model lists.
6.  **Step 6**: Testing and verification.
