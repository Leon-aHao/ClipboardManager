import os
from datetime import datetime


class TempFileManager:
    def __init__(self, temp_dir: str = None):
        if temp_dir is None:
            temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "ClipboardManager")
        self._temp_dir = temp_dir
        os.makedirs(self._temp_dir, exist_ok=True)

    def create_temp_file(self, image_data: bytes, name_hint: str = None) -> str:
        if name_hint:
            safe_name = "".join(c for c in name_hint if c.isalnum() or c in "._- ")
            safe_name = safe_name.strip() or "clipboard_image"
        else:
            safe_name = f"clipboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path = os.path.join(self._temp_dir, f"{safe_name}.png")
        counter = 1
        while os.path.exists(path):
            path = os.path.join(self._temp_dir, f"{safe_name}_{counter}.png")
            counter += 1
        with open(path, "wb") as f:
            f.write(image_data)
        return path

    def cleanup(self, max_age_seconds: int = 3600):
        now = datetime.now().timestamp()
        try:
            for fname in os.listdir(self._temp_dir):
                fpath = os.path.join(self._temp_dir, fname)
                if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > max_age_seconds:
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
        except OSError:
            pass
