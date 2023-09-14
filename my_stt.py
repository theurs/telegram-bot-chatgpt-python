#!/usr/bin/env python3


import os
import subprocess
import tempfile
import speech_recognition as sr

import my_log


def convert_to_wave_with_ffmpeg(audio_file: str) -> str:
    """
    Converts an audio file to a wave format using FFmpeg.

    Args:
        audio_file (str): The path to the audio file to be converted.

    Returns:
        str: The path to the converted wave file.
    """
    with tempfile.NamedTemporaryFile() as temp_file:
        tmp_wav_file = temp_file.name + '.wav'
    subprocess.run(['ffmpeg', '-i', audio_file, tmp_wav_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return tmp_wav_file


def audio_duration(audio_file: str) -> int:
    """
    Get the duration of an audio file.

    Args:
        audio_file (str): The path to the audio file.

    Returns:
        int: The duration of the audio file in seconds.
    """
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout)


def stt_google(audio_file: str, language: str) -> str:
    """
    Speech-to-text using Google's speech recognition API.
    
    Args:
        audio_file (str): The path to the audio file to be transcribed.
        language (str, optional): The language of the audio file. Defaults to 'ru'.
    
    Returns:
        str: The transcribed text from the audio file.
    """
    assert audio_duration(audio_file) < 55, 'Too big for free speech recognition'
    audio_file2 = convert_to_wave_with_ffmpeg(audio_file)
    google_recognizer = sr.Recognizer()

    with sr.AudioFile(audio_file2) as source:
        audio = google_recognizer.record(source)  # read the entire audio file

    text = google_recognizer.recognize_google(audio, language=language)

    os.remove(audio_file2)

    return text


def stt(input_file: str, lang: str) -> str:
    """
    Generate the function comment for the given function body in a markdown code block with the correct language syntax.

    Args:
        input_file (str): The input file to be processed.
        lang (str): The language of the input file.

    Returns:
        str: The text generated from the input file.

    Raises:
        AssertionError: If an assertion error occurs during the execution.
        sr.UnknownValueError: If an unknown value error occurs during the execution.
        sr.RequestError: If a request error occurs during the execution.
        Exception: If any other unknown error occurs during the execution.
    """
    text = ''

    try:
       text = stt_google(input_file, lang)
    except AssertionError:
        pass
    except sr.UnknownValueError as unknown_value_error:
        print(unknown_value_error)
        my_log.log2(str(unknown_value_error))
    except sr.RequestError as request_error:
        print(request_error)
        my_log.log2(str(request_error))
    except Exception as unknown_error:
        print(unknown_error)
        my_log.log2(str(unknown_error))

    return text


if __name__ == "__main__":
    pass