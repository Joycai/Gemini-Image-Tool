import string
from typing import Optional


def text_encoder(input_str : Optional[string]) -> Optional[string] :
    if input_str:
        utf8_bytes = input_str.encode('utf-8')
        return utf8_bytes.decode('utf-8')
    else:
        return None