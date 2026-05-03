import cv2
from object_detection import ObjectDetector
from pose_detector import PoseDetector
from decision_engine import DecisionEngine
from tracker import Tracker
from utils.matcher import Matcher


class StreamProcessor:
    """
    Production-ready stream processor (Flask compatible)

    RULE:
    - ONLY show CHEATING cases (red boxes)
    - NORMAL students are NOT visualized
    """

    def __init__(self):
        self.obj_detector = ObjectDetector()
        self.pose_detector = PoseDetector()
        self.tracker = Tracker()
        self.decision_engine = DecisionEngine()
        self.matcher = Matcher()

    # ---------------------------------------------------
    # PROCESS FRAME
    # ---------------------------------------------------
    def process_frame(self, frame):

        # 1️⃣ OBJECT DETECTION
        detections = self.obj_detector.detect(frame)

        # 2️⃣ TRACKING
        tracked_persons = self.tracker.update(detections, frame)

        # 3️⃣ POSE DETECTION
        poses = self.pose_detector.detect(frame)

        # 4️⃣ MATCH POSE WITH PERSONS
        pose_map = self.matcher.match(tracked_persons, poses)
        poses_list = list(pose_map.values())

        # 5️⃣ DECISION ENGINE
        result = self.decision_engine.evaluate(
            detections,
            poses_list,
            tracked_persons,
            frame
        )

        # 6️⃣ DRAW ONLY CHEATING CASES
        frame = self._draw(frame, tracked_persons, result)

        return frame, result

    # ---------------------------------------------------
    # DRAW ONLY CHEATING
    # ---------------------------------------------------
    def _draw(self, frame, tracked_persons, result):

        cheating_ids = result.get("cheating_ids", [])

        # 🔴 ONLY CHEATING BOXES
        for person in tracked_persons:

            pid = person["id"]

            # ❌ SKIP NORMAL PEOPLE COMPLETELY
            if pid not in cheating_ids:
                continue

            x1, y1, x2, y2 = person["box"]

            # RED BOX ONLY
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)

            cv2.putText(
                frame,
                f"CHEATING ID: {pid}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        # GLOBAL STATUS (optional but useful)
        status_color = (0, 0, 255) if result["status"] == "CHEATING" else (200, 200, 200)

        cv2.putText(
            frame,
            f"STATUS: {result['status']}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            status_color,
            2
        )

        return frame