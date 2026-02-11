from detection.point_detection.inference import PointDetInference
from detection.segmentation.inference_two_stage import TwoStageInference

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

        data_dict = {
            "frame": frame,
            "points": points,
            "inner_points": inner_points,
            "overlap_points": overlap_points,
            "polygons": polygons
        }
        return data_dict
    
