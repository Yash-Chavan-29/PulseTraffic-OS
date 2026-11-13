"""
PulseTraffic OS - Vehicle Tracking Module
Provides multi-object tracking (ByteTrack / Centroid & IoU association)
to track vehicles across frames, prevent duplicate counts, and measure dwell time.
"""

import math
from typing import Dict, List, Tuple, Optional

def calculate_iou(boxA: List[int], boxB: List[int]) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return iou

class TrackedVehicle:
    def __init__(self, track_id: int, bbox: List[int], vehicle_type: str, confidence: float, direction: str, lane_id: int):
        self.track_id = track_id
        self.bbox = bbox
        self.vehicle_type = vehicle_type
        self.confidence = confidence
        self.direction = direction
        self.lane_id = lane_id
        self.centroid = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
        self.history: List[Tuple[float, float]] = [self.centroid]
        self.disappeared_frames = 0
        self.total_frames = 1
        self.dwell_time_sec = 0.0
        self.counted = False
        self.speed_px_per_sec = 0.0

    def update(self, bbox: List[int], confidence: float, fps: float = 30.0):
        self.bbox = bbox
        self.confidence = confidence
        new_centroid = ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)
        
        # Calculate speed estimate in pixels
        dx = new_centroid[0] - self.centroid[0]
        dy = new_centroid[1] - self.centroid[1]
        dist = math.hypot(dx, dy)
        self.speed_px_per_sec = dist * fps

        self.centroid = new_centroid
        self.history.append(new_centroid)
        if len(self.history) > 30:
            self.history.pop(0)

        self.disappeared_frames = 0
        self.total_frames += 1
        self.dwell_time_sec += (1.0 / max(1.0, fps))

class VehicleTracker:
    def __init__(self, max_disappeared: int = 15, iou_threshold: float = 0.3):
        self.next_track_id = 1
        self.tracks: Dict[int, TrackedVehicle] = {}
        self.max_disappeared = max_disappeared
        self.iou_threshold = iou_threshold

    def update(self, detections: List[Dict], fps: float = 30.0) -> List[TrackedVehicle]:
        """
        Takes raw detections for current frame:
        [{"bbox": [x1, y1, x2, y2], "class": "car", "confidence": 0.88, "direction": "north", "lane_id": 1}]
        Updates active tracks using IoU & spatial proximity.
        """
        if len(detections) == 0:
            for track_id in list(self.tracks.keys()):
                self.tracks[track_id].disappeared_frames += 1
                if self.tracks[track_id].disappeared_frames > self.max_disappeared:
                    del self.tracks[track_id]
            return list(self.tracks.values())

        if len(self.tracks) == 0:
            for det in detections:
                self._register(det)
            return list(self.tracks.values())

        # Match existing tracks with detections via IoU matrix
        track_ids = list(self.tracks.keys())
        det_indices = list(range(len(detections)))

        iou_matrix = []
        for tid in track_ids:
            row = [calculate_iou(self.tracks[tid].bbox, detections[d_idx]["bbox"]) for d_idx in det_indices]
            iou_matrix.append(row)

        matched_tracks = set()
        matched_dets = set()

        # Greedy match highest IoU pairs
        while True:
            max_iou = 0.0
            best_pair = None
            for r, tid in enumerate(track_ids):
                if tid in matched_tracks:
                    continue
                for c, d_idx in enumerate(det_indices):
                    if d_idx in matched_dets:
                        continue
                    if iou_matrix[r][c] > max_iou:
                        max_iou = iou_matrix[r][c]
                        best_pair = (tid, d_idx)

            if best_pair and max_iou >= self.iou_threshold:
                tid, d_idx = best_pair
                self.tracks[tid].update(detections[d_idx]["bbox"], detections[d_idx]["confidence"], fps=fps)
                self.tracks[tid].direction = detections[d_idx]["direction"]
                self.tracks[tid].lane_id = detections[d_idx]["lane_id"]
                matched_tracks.add(tid)
                matched_dets.add(d_idx)
            else:
                break

        # Mark unmatched tracks as disappeared
        for tid in track_ids:
            if tid not in matched_tracks:
                self.tracks[tid].disappeared_frames += 1
                if self.tracks[tid].disappeared_frames > self.max_disappeared:
                    del self.tracks[tid]

        # Register new tracks for unmatched detections
        for d_idx in det_indices:
            if d_idx not in matched_dets:
                self._register(detections[d_idx])

        return list(self.tracks.values())

    def _register(self, det: Dict):
        new_track = TrackedVehicle(
            track_id=self.next_track_id,
            bbox=det["bbox"],
            vehicle_type=det["class"],
            confidence=det["confidence"],
            direction=det["direction"],
            lane_id=det["lane_id"]
        )
        self.tracks[self.next_track_id] = new_track
        self.next_track_id += 1
