from datetime import datetime
from util.file import File
from detection.point_detection.inference import PointDetInference
from detection.segmentation.inference_two_stage import TwoStageInference
from config import file_const

class Inspection():    
    def temporary(self, frame):
        # inference (point detection & segmentation)

        # point, inner, overlap (point detection)
        pdi = PointDetInference()
        points_data = pdi.predict(frame)
        points = points_data["points"]
        inner_points = points_data["inner"]
        overlap_points = points_data["overlap"]

        # polygon (segmentation)
        tsi = TwoStageInference()
        polygons = tsi.predict(frame)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        img_name = f"IMG_{timestamp}.{file_const.JPG_EXTENSION}"

        file = File()
        file.save_jpg(frame, timestamp)
        data_dict = {
            "img_name": img_name,
            "frame": frame,
            "points": points,
            "inner_points": inner_points,
            "overlap_points": overlap_points,
            "polygons": polygons
        }
        return data_dict
    
