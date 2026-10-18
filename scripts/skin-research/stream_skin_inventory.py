"""Stream the existing JSON rows; annotations/photos never form a RAM pool."""
import json,re
def inventory_rows(path):
    decoder=json.JSONDecoder()
    with path.open(encoding='utf8') as file:
        text=file.read(65536);match=re.search(r'"rows"\s*:\s*\[',text)
        if not match:raise ValueError('Unsupported inventory rows contract')
        text=text[match.end():]
        while True:
            text=text.lstrip(' \r\n\t,')
            if text.startswith(']'):return
            try:row,end=decoder.raw_decode(text)
            except json.JSONDecodeError:
                chunk=file.read(65536)
                if not chunk:raise ValueError('Incomplete source inventory')
                text+=chunk;continue
            yield row;text=text[end:]
