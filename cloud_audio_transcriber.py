import os
import io
import threading
import logging
from pydub import AudioSegment
import whisper
from faster_whisper import WhisperModel
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive']
AUDIO_FORMATS = ('.mp3', '.wav', '.m4a')
MAX_DURATION_MS = 10 * 60 * 1000  # 10 minutes
DOWNLOAD_DIR = 'downloads'
TRANSCRIPT_DIR = 'transcripts'
MODEL_NAME = 'base'

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate():
    creds = None

    # Check if token exists and is valid
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if creds and creds.valid:
            return creds
        elif creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                return creds
            except RefreshError:
                print("Token expired and cannot be refreshed. Re-authenticating...")

    # If no valid credentials, run interactive OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    flow.redirect_uri = 'http://localhost'  # ✅ Set the redirect_uri manually

    # Try run_console() if available
    try:
        print("Attempting headless authentication via run_console()...")
        creds = flow.run_console()
    except AttributeError:
        # Fallback to manual URL + input method
        print("run_console() not available. Using manual authorization flow...")
        auth_url, _ = flow.authorization_url(prompt='consent')

        print(f"\nPlease go to this URL:\n{auth_url}")
        code = input("Enter the authorization code here: ")
        flow.fetch_token(code=code)
        creds = flow.credentials

    # Save credentials for future use
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

    return creds

def download_audio_files(service, folder_id):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    query = f"'{folder_id}' in parents and mimeType contains 'audio/'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    file_paths = []

    for item in items:
        file_id = item['id']
        file_name = item['name']
        if not file_name.endswith(AUDIO_FORMATS):
            continue

        file_path = os.path.join(DOWNLOAD_DIR, file_name)

        if os.path.exists(file_path):
            logging.info(f"Skipping download. {file_name} already exists.")
        else:
            logging.info(f"Downloading {file_name}...")
            request = service.files().get_media(fileId=file_id)
            with open(file_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                start_time = time.time()
                while not done:
                    if time.time() - start_time > 3600:  # 1 hour timeout
                        raise TimeoutError(f"Download timed out for {file_name}")
                    status, done = downloader.next_chunk()

        file_paths.append((file_path, file_id))

    return file_paths


def split_audio(file_path):
    audio = AudioSegment.from_file(file_path)
    duration_ms = len(audio)
    base_name, _ = os.path.splitext(os.path.basename(file_path))

    # If no split is needed
    if duration_ms <= MAX_DURATION_MS:
        return [file_path]

    # Calculate how many parts we need
    num_parts = (duration_ms + MAX_DURATION_MS - 1) // MAX_DURATION_MS
    expected_chunk_paths = [
        os.path.join(DOWNLOAD_DIR, f"{base_name}_part{i + 1}.mp3")
        for i in range(num_parts)
    ]

    # Check if all chunks already exist
    if all(os.path.exists(path) for path in expected_chunk_paths):
        return expected_chunk_paths

    # Otherwise, split the audio
    chunks = []
    for i in range(num_parts):
        start = i * MAX_DURATION_MS
        end = min(start + MAX_DURATION_MS, duration_ms)
        part = audio[start:end]
        part.export(expected_chunk_paths[i], format='mp3')
        chunks.append(expected_chunk_paths[i])

    return chunks

  
def transcribe_file(model, file_path, transcript_dir):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    transcript_path = os.path.join(transcript_dir, f"{base_name}.txt")
    logging.info(f"Transcribing {base_name}...")

    try:
        # Faster-Whisper transcription
        segments, info = model.transcribe(
            file_path,
            task="transcribe",
            without_timestamps=True,
            beam_size=5 # Smaller = faster, larger = more accurate (default 5)
        )
        # Log language info if available
        if info and hasattr(info, 'language'):
            logging.info(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

        # Combine all segments into single text
        full_text = " ".join(segment.text for segment in segments)
        
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        return transcript_path
    
    except Exception as e:
        logging.error(f"Error processing {file_path}: {str(e)}")
        raise

def transcribe_files(file_paths, service, transcript_folder_id):
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    #model = whisper.load_model(MODEL_NAME, device="cpu") # Ensures FP32 is used
    model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8", download_root="whisper_models") # int8 = optimized for CPU # Optional: Custom model cache location
    print(f"Loaded Whisper model: {MODEL_NAME}")
    
    transcript_paths = []
    
    for file_path in file_paths:
        try:
            print(f"Processing {file_path}")
            transcript = transcribe_file(model, file_path, TRANSCRIPT_DIR)
            print(f"Transcription complete for {file_path}")
            
            #upload_files(service, transcript_folder_id, transcript)
            #os.remove(file_path)
            #print(f"Cleaned up {file_path}")
            
            transcript_paths.append(transcript)
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            logging.exception(f"Failed to process {file_path}")
    
    return transcript_paths

def combine_transcripts(file_paths, original_file):
    base_name = os.path.splitext(os.path.basename(original_file))[0]
    combined_path = os.path.join(TRANSCRIPT_DIR, f"{base_name}_FULL.txt")
    with open(combined_path, 'w', encoding='utf-8') as outfile:
        for file_path in file_paths:
            with open(file_path, 'r', encoding='utf-8') as infile:
                outfile.write(infile.read() + '\n')
    return combined_path

def upload_files(service, folder_id, file_paths):
    for file_path in file_paths:
        file_name = os.path.basename(file_path)
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        logging.info(f"Uploaded {file_name}")

def cleanup(files):
    for file in files:
        os.remove(file)
        logging.info(f"Deleted {file}")

def main():
    try:
        creds = authenticate()
        service = build('drive', 'v3', credentials=creds)

        audio_files = download_audio_files(service, FOLDER_ID)
        all_transcripts = []

        for file_path, _ in audio_files:
            print(f"Processing {file_path}")
            parts = split_audio(file_path)
            print(f"Split into {len(parts)} parts")
            
            transcripts = transcribe_files(parts, service, FOLDER_ID)
            print(f"Generated {len(transcripts)} transcripts")
            
            if transcripts:
                combined = combine_transcripts(transcripts, file_path)
                upload_files(service, FOLDER_ID, transcripts + [combined])
                cleanup(parts + transcripts + [combined, file_path])
    
    except Exception as e:
        logging.exception("Fatal error in main:")
        raise

if __name__ == '__main__':
    main()
