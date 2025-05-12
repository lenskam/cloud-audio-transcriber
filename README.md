# Cloud Audio Transcriber

A Python application that:

- Connects to your Google Drive and downloads audio files.
- Splits large audio files into smaller parts.
- Transcribes audio files using OpenAI's Whisper.
- Uploads transcripts back to Google Drive.
- Designed to run seamlessly on GitHub Codespaces.

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/lenskam/cloud-audio-transcriber.git
   cd cloud-audio-transcriber
    ```

2. Create a .env file:

    ```bash
    cp .env.example .env
    ```
    Replace your_folder_id_here with your actual Google Drive folder ID.

3. Add your credentials.json file obtained from **Google Cloud Console** to the project root by creating and OAuth Client ID of type `Desktop app`.

4. Open the project in GitHub Codespaces.

Run the setup script if it doesn't run to devcontainer startup:

    
    bash .devcontainer/install.sh
    

## Usage
Run the main script:

    python cloud_audio_transcriber.py

     
## Notes
Ensure that the `credentials.json` file is present in the project root.