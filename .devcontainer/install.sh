#!/bin/bash
sudo apt-get update
sudo apt-get install -y ffmpeg
pip install --upgrade pip
pip install -r requirements.txt
pip install git+https://github.com/openai/whisper.git
