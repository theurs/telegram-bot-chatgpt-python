#!/usr/bin/env python3


import io
import glob
import os

import gtts

import my_log


# cleanup
for filePath in [x for x in glob.glob('*.wav') + glob.glob('*.ogg') if 'temp_tts_file' in x]:
    try:
        os.remove(filePath)
    except Exception as error:
        my_log.log2(f"Error while deleting file : {filePath}\n\n{error}")


def tts_google(text: str, lang: str) -> bytes:
    """
    Converts the given text to speech using the Google Text-to-Speech (gTTS) API.

    Parameters:
        text (str): The text to be converted to speech.
        lang (str, optional): The language of the text. Defaults to 'ru'.

    Returns:
        bytes: The audio file in the form of bytes.
    """
    mp3_fp = io.BytesIO()
    result = gtts.gTTS(text, lang=lang)
    result.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return mp3_fp.read()


def tts(text: str, lang: str) -> bytes:
    text = text.replace('\r','') 
    text = text.replace('\n\n','\n')  

    return tts_google(text, lang)


if __name__ == "__main__":
    pass