from pathlib import Path
from datetime import datetime

from util.file import File

class History():

    def __init__(self):
        self.file = File()

    # 불러온 .jpg 파일명, 검사시간으로 반환 / 시작 화면
    def get_all_jpg(self):
        jpg_files, path = self.file.get_all_jpg()

        file_names_with_ext = [f.name for f in jpg_files]

        formatted_list = [
            f"{f[4:8]}-{f[8:10]}-{f[10:12]} {f[13:15]}:{f[15:17]}:{f[17:19]}.{f[20:23]}"
            for f in file_names_with_ext
        ]

        return file_names_with_ext, formatted_list, path


    # .jpg / .json 파일 불러오기 / 파일명 클릭 시
    def get_jpg_json_by_filename(self, filename):
        if "-" in filename:
            date_part = filename[0:4] + filename[5:7] + filename[8:10]
            time_part = filename[11:13] + filename[14:16] + filename[17:19]
            ms_part = filename[20:23]

            filename = f"IMG_{date_part}_{time_part}_{ms_part}"

        pure_name = Path(filename).stem
        
        frame, json_data = self.file.get_jpg_json_by_filename(pure_name)

        return frame, json_data

    # .jpg 파일 불러오기 / 보기 기능
    def get_jpg(self, filename):
        jpg_path = self.file.get_jpg(filename)

        return jpg_path

    # .jpg / .json 파일 삭제 / 삭제 기능
    def delete_jpg_json(self, filename):
        pure_name = Path(filename).stem

        img_path, json_path = self.file.delete_jpg_json(pure_name)

        return img_path, json_path

    # 폴더 열기
    def get_path(self):
        path = self.file.get_path()

        return path
    
    # 로그 내보내기
    def get_log(self):
        log = []
        
        jpg_files, json_files = self.file.get_all_jpg_json()

        file_names_with_ext = [f.name for f in jpg_files]

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for filename, result in zip(file_names_with_ext, json_files):
            record = {
                "filename": filename,
                "result": result,
                "exported_at": timestamp
            }

            log.append(record)

        timestamp = datetime.now().strftime("%Y%m%d")
        
        return log, timestamp
    
    # 불러온 .jpg 파일명, 검사시간으로 반환
    def get_last_img(self):
        jpg_file, path = self.file.get_last_img()

        f = jpg_file.name

        formatted_time = f"{f[4:8]}-{f[8:10]}-{f[10:12]} {f[13:15]}:{f[15:17]}:{f[17:19]}.{f[20:23]}"

        return f, formatted_time, path