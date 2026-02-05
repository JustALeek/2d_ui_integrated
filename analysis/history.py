"""
Utility class for managing inspection history data including images and metadata.
Provides parsing logic for filename-based timestamps and interfaces with the underlying file system.
Facilitates data retrieval for UI display, log export, and file management.
"""

from pathlib import Path
from datetime import datetime

from util.file import File

class History():

    def __init__(self):
        """Initializes the History manager by linking the file utility module."""
        self.file = File()

    def get_all_jpg(self):
        """Retrieves all JPEG files and parses filenames into formatted timestamps for the startup screen."""
        jpg_files, path = self.file.get_all_jpg()

        file_names_with_ext = [f.name for f in jpg_files]

        formatted_list = [
            f"{f[4:8]}-{f[8:10]}-{f[10:12]} {f[13:15]}:{f[15:17]}:{f[17:19]}.{f[20:23]}"
            for f in file_names_with_ext
        ]

        return file_names_with_ext, formatted_list, path

    # .jpg 파일 불러오기 / 보기 기능
    def get_jpg(self, filename):
        if "-" in filename:
            date_part = filename[0:4] + filename[5:7] + filename[8:10]
            time_part = filename[11:13] + filename[14:16] + filename[17:19]
            ms_part = filename[20:23]

            filename = f"IMG_{date_part}_{time_part}_{ms_part}"

        jpg_path = self.file.get_jpg(filename)

        return jpg_path

    # 폴더 열기
    def get_path(self):
        path = self.file.get_path()

        return path
    
    # 로그 내보내기
    def get_log(self):
        log = []

        jpg_files, _ = self.file.get_all_jpg()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for f in jpg_files:
            log.append({
                "filename": f.name,
                "exported_at": timestamp
            })

        date_stamp = datetime.now().strftime("%Y%m%d")

        return log, date_stamp
    
    def get_last_img(self):
        """Retrieves and formats the most recently captured image for UI update."""
        # Fetch the latest image and parse its time information
        jpg_file, path = self.file.get_last_img()
        f = jpg_file.name

        # Convert raw filename to display timestamp format
        formatted_time = f"{f[4:8]}-{f[8:10]}-{f[10:12]} {f[13:15]}:{f[15:17]}:{f[17:19]}.{f[20:23]}"

        return f, formatted_time, path