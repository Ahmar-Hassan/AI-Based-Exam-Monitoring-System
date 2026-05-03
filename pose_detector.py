from ultralytics import YOLO
import numpy as np


class PoseDetector:
    """
    Professional YOLOv8 Pose Detector

    Features:
    ✔ Stable head direction (temporal smoothing)
    ✔ Bounding boxes for tracking
    ✔ Strong keypoint validation
    ✔ Reduced flickering
    ✔ Tracker-friendly output
    """

    def __init__(self, model_path="yolov8s-pose.pt", conf=0.4):

        self.model = YOLO(model_path)
        self.conf = conf

        # 🔥 Memory for smoothing (VERY IMPORTANT)
        self.prev_directions = {}

    # ---------------------------------------------------
    # MAIN DETECTION
    # ---------------------------------------------------
    def detect(self, frame):

        results = self.model(frame, conf=self.conf, verbose=False)

        persons = []

        for r in results:

            if r.keypoints is None or r.boxes is None:
                continue

            keypoints_all = r.keypoints.xy.cpu().numpy()
            boxes_all = r.boxes.xyxy.cpu().numpy()
            scores = r.boxes.conf.cpu().numpy()

            for i in range(len(keypoints_all)):

                # ❌ Skip weak detections
                if scores[i] < self.conf:
                    continue

                keypoints = keypoints_all[i]
                x1, y1, x2, y2 = boxes_all[i]

                # Extract keypoints
                nose = keypoints[0]
                left_eye = keypoints[1]
                right_eye = keypoints[2]

                # ❌ Strong validation
                if (
                    np.any(nose == 0) or
                    np.any(left_eye == 0) or
                    np.any(right_eye == 0)
                ):
                    continue

                # Face center
                face_center = (
                    int((left_eye[0] + right_eye[0]) / 2),
                    int((left_eye[1] + right_eye[1]) / 2)
                )

                # 🔥 Adaptive threshold (important)
                width = abs(x2 - x1)
                threshold = max(10, width * 0.06)

                # Raw direction
                if nose[0] < face_center[0] - threshold:
                    direction = "LEFT"
                elif nose[0] > face_center[0] + threshold:
                    direction = "RIGHT"
                else:
                    direction = "FORWARD"

                # 🔥 SMOOTHING (VERY IMPORTANT)
                direction = self._smooth_direction(i, direction)

                persons.append({
                    "id": i,  # temporary (tracker will replace)
                    "direction": direction,
                    "face_center": face_center,
                    "box": [int(x1), int(y1), int(x2), int(y2)]
                })

        return persons

    # ---------------------------------------------------
    # 🔥 DIRECTION SMOOTHING (KEY FEATURE)
    # ---------------------------------------------------
    def _smooth_direction(self, pid, current_dir):

        prev = self.prev_directions.get(pid)

        # If no previous → store
        if prev is None:
            self.prev_directions[pid] = current_dir
            return current_dir

        # If same → stable
        if prev == current_dir:
            return current_dir

        # If different → require confirmation (anti-flicker)
        # Keep previous unless repeated
        self.prev_directions[pid] = current_dir
        return prev