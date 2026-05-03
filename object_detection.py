from ultralytics import YOLO
import cv2
import time


class ObjectDetector:


    def __init__(
        self,
        model_path="yolov8s.pt",  
        confidence=0.4,
        device="cpu",
        debug=False
    ):

        self.model = YOLO(model_path)
        self.model.to(device)

        self.confidence = confidence
        self.debug = debug

        # COCO class IDs
        self.target_class_ids = [0, 67]  # person, cell phone

        # FPS tracking
        self.prev_time = time.time()

    # ---------------------------------------------------
    # MAIN DETECTION FUNCTION
    # ---------------------------------------------------
    def detect(self, frame):

        detections = []

        if frame is None:
            return detections

        try:
            results = self.model(
                frame,
                conf=self.confidence,
                classes=self.target_class_ids,
                verbose=False
            )

            detections = self._process_results(results, frame)

        except Exception as e:
            print(f"⚠ Detection Error: {e}")

        return detections

    # ---------------------------------------------------
    # PROCESS YOLO OUTPUT
    # ---------------------------------------------------
    def _process_results(self, results, frame):

        detections = []

        for r in results:

            if r.boxes is None:
                continue

            for box in r.boxes:

                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                label = "person" if cls_id == 0 else "cell phone"

                det = {
                    "label": label,
                    "confidence": round(conf, 3),
                    "box": [x1, y1, x2, y2]
                }

                detections.append(det)

                if self.debug:
                    self._draw_debug(frame, label, conf, x1, y1, x2, y2)

        return detections

    # ---------------------------------------------------
    # DEBUG VISUALIZATION
    # ---------------------------------------------------
    def _draw_debug(self, frame, label, conf, x1, y1, x2, y2):

        color = (0, 255, 0) if label == "person" else (0, 0, 255)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        cv2.putText(
            frame,
            f"{label} {conf:.2f}",
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2
        )

    # ---------------------------------------------------
    # OBJECT COUNTER
    # ---------------------------------------------------
    def count_objects(self, detections, label):
        return sum(1 for d in detections if d["label"] == label)

    # ---------------------------------------------------
    # FPS MONITOR
    # ---------------------------------------------------
    def get_fps(self):

        current_time = time.time()
        fps = 1 / (current_time - self.prev_time)
        self.prev_time = current_time

        return round(fps, 2)