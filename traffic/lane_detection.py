"""
PulseTraffic OS - Lane Detection and Spatial Region Mapping
Maps 2D pixel coordinates and camera bounding boxes to specific lanes
and directional approaches (North, South, East, West).
"""

from typing import Dict, List, Tuple, Optional
import math

class LaneRegion:
    def __init__(self, lane_id: int, name: str, direction: str, polygon: List[Tuple[int, int]]):
        self.lane_id = lane_id
        self.name = name
        self.direction = direction.lower()  # 'north', 'south', 'east', 'west'
        self.polygon = polygon  # List of (x, y) coordinates defining lane boundary

    def contains_point(self, point: Tuple[float, float]) -> bool:
        """Ray-casting algorithm to test if point is inside lane polygon."""
        x, y = point
        n = len(self.polygon)
        inside = False
        p1x, p1y = self.polygon[0]
        for i in range(n + 1):
            p2x, p2y = self.polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

class LaneDetector:
    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.lanes: List[LaneRegion] = []
        self._initialize_default_geometry()

    def _initialize_default_geometry(self):
        """Creates calibrated 4-way intersection lane regions."""
        w, h = self.frame_width, self.frame_height
        cx, cy = w // 2, h // 2

        # North Approach (Top vertical corridor coming south)
        self.lanes.append(LaneRegion(
            lane_id=1, name="North Straight/Left", direction="north",
            polygon=[(cx - 140, 0), (cx - 10, 0), (cx - 10, cy - 80), (cx - 140, cy - 80)]
        ))
        self.lanes.append(LaneRegion(
            lane_id=2, name="North Right-Turn Pocket", direction="north",
            polygon=[(cx - 10, 0), (cx + 60, 0), (cx + 60, cy - 80), (cx - 10, cy - 80)]
        ))

        # South Approach (Bottom vertical corridor coming north)
        self.lanes.append(LaneRegion(
            lane_id=3, name="South Straight/Left", direction="south",
            polygon=[(cx + 10, cy + 80), (cx + 140, cy + 80), (cx + 140, h), (cx + 10, h)]
        ))
        self.lanes.append(LaneRegion(
            lane_id=4, name="South Right-Turn Pocket", direction="south",
            polygon=[(cx - 60, cy + 80), (cx + 10, cy + 80), (cx + 10, h), (cx - 60, h)]
        ))

        # East Approach (Right horizontal corridor coming west)
        self.lanes.append(LaneRegion(
            lane_id=5, name="East Straight/Left", direction="east",
            polygon=[(cx + 80, cy - 120), (w, cy - 120), (w, cy - 10), (cx + 80, cy - 10)]
        ))
        self.lanes.append(LaneRegion(
            lane_id=6, name="East Right-Turn Pocket", direction="east",
            polygon=[(cx + 80, cy - 10), (w, cy - 10), (w, cy + 60), (cx + 80, cy + 60)]
        ))

        # West Approach (Left horizontal corridor coming east)
        self.lanes.append(LaneRegion(
            lane_id=7, name="West Straight/Left", direction="west",
            polygon=[(0, cy + 10), (cx - 80, cy + 10), (cx - 80, cy + 120), (0, cy + 120)]
        ))
        self.lanes.append(LaneRegion(
            lane_id=8, name="West Right-Turn Pocket", direction="west",
            polygon=[(0, cy - 60), (cx - 80, cy - 60), (cx - 80, cy + 10), (0, cy + 10)]
        ))

    def assign_lane(self, bbox: List[int]) -> Optional[Tuple[str, int, str]]:
        """
        Given a bounding box [x1, y1, x2, y2], computes the bottom-center
        contact point with the road and determines its matching lane and direction.
        Returns: (direction, lane_id, lane_name) or None if outside calibrated lanes.
        """
        x1, y1, x2, y2 = bbox
        bottom_center = ((x1 + x2) / 2.0, float(y2))

        for lane in self.lanes:
            if lane.contains_point(bottom_center):
                return lane.direction, lane.lane_id, lane.name

        # Fallback quadrant assignment if vehicle is slightly outside designated polygon
        cx, cy = self.frame_width // 2, self.frame_height // 2
        bx, by = bottom_center
        if by < cy - 60:
            return "north", 1, "North Approach"
        elif by > cy + 60:
            return "south", 3, "South Approach"
        elif bx > cx + 60:
            return "east", 5, "East Approach"
        elif bx < cx - 60:
            return "west", 7, "West Approach"

        return None
