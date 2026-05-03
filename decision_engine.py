import cv2
import math
from datetime import datetime


class DecisionEngine:

    def __init__(self, snapshot_dir="snapshots"):

        # 🔥 Tuned thresholds
        self.interaction_threshold = 140

        self.snapshot_dir = snapshot_dir

    # ---------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------
    def save_snapshot(self, frame, reason):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.snapshot_dir}/{timestamp}_{reason}.jpg"
        cv2.imwrite(filename, frame)
        return filename

    # ---------------------------------------------------
    # HELPER: FIND NEAREST PERSON TO PHONE
    # ---------------------------------------------------
    def _find_nearest_person(self, phone_box, persons):

        px1, py1, px2, py2 = phone_box
        pcx = (px1 + px2) // 2
        pcy = (py1 + py2) // 2

        min_dist = float("inf")
        best_id = None

        for person in persons:
            x1, y1, x2, y2 = person["box"]
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            dist = math.hypot(cx - pcx, cy - pcy)

            if dist < min_dist:
                min_dist = dist
                best_id = person["id"]

        return best_id

    # ---------------------------------------------------
    # MAIN LOGIC (INSTANT + SMART)
    # ---------------------------------------------------
    def evaluate(self, detections, poses, tracked_persons, frame=None):

        cheating_ids = []
        snapshot_file = None

        # =========================================
        # RULE 1 — PHONE (VERY STRONG CHEATING)
        # =========================================
        phones = [d for d in detections if d["label"] == "cell phone"]

        if phones and tracked_persons:

            person_id = self._find_nearest_person(phones[0]["box"], tracked_persons)

            if person_id is not None:
                cheating_ids.append(person_id)

            if frame is not None:
                snapshot_file = self.save_snapshot(frame, "phone")

            return {
                "status": "CHEATING",
                "reason": f"Person {person_id} using phone",
                "score": 100,
                "snapshot": snapshot_file,
                "cheating_ids": cheating_ids
            }

        # =========================================
        # RULE 2 — INSTANT LOOK AWAY (NO DELAY)
        # =========================================
        for face in poses:

            pid = face["id"]
            direction = face["direction"]

            # 🔥 Instant trigger
            if direction in ["LEFT", "RIGHT"]:

                cheating_ids.append(pid)

                if frame is not None:
                    snapshot_file = self.save_snapshot(frame, f"look_{pid}")

                return {
                    "status": "SUSPICIOUS",
                    "reason": f"Person {pid} looking {direction}",
                    "score": 60,
                    "snapshot": snapshot_file,
                    "cheating_ids": cheating_ids
                }

        # =========================================
        # RULE 3 — INTERACTION (RELAXED)
        # =========================================
        for i in range(len(poses)):
            for j in range(i + 1, len(poses)):

                f1 = poses[i]
                f2 = poses[j]

                p1, p2 = f1["id"], f2["id"]

                x1, y1 = f1["face_center"]
                x2, y2 = f2["face_center"]

                distance = math.hypot(x2 - x1, y2 - y1)

                # 🔥 relaxed detection
                if distance < self.interaction_threshold:

                    if f1["direction"] != "FORWARD" or f2["direction"] != "FORWARD":

                        cheating_ids.extend([p1, p2])

                        if frame is not None:
                            snapshot_file = self.save_snapshot(
                                frame,
                                f"interaction_{p1}_{p2}"
                            )

                        return {
                            "status": "SUSPICIOUS",
                            "reason": f"Persons {p1} & {p2} interacting",
                            "score": 70,
                            "snapshot": snapshot_file,
                            "cheating_ids": cheating_ids
                        }

        # =========================================
        # DEFAULT
        # =========================================
        return {
            "status": "NORMAL",
            "reason": "No suspicious activity",
            "score": 0,
            "snapshot": None,
            "cheating_ids": []
        }