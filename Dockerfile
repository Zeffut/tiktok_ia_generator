FROM python:3.9.9

WORKDIR /app
COPY . /app

RUN apt-get update -y && apt-get upgrade -y
RUN apt-get install -y ffmpeg
RUN pip install pytube pydub ffmpeg moviepy openai-whisper youtube-transcript-api openai selenium undetected_chromedriver markdownify pyperclip pyautogui

CMD [ "python", "main.py" ]