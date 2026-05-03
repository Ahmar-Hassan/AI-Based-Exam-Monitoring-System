from deep_sort_realtime.deepsort_tracker import DeepSort


class Tracker:
    """
    DeepSORT Tracker

    Features:
    - Stable ID tracking
    - Handles occlusion
    - Works with YOLO detections
    """

    def __init__(self):
        self.tracker = DeepSort(
            max_age=30,
            n_init=2,
            max_cosine_distance=0.3
        )

    # ---------------------------------------------------
    # UPDATE TRACKER
    # ---------------------------------------------------
    def update(self, detections, frame):
        

        dets = []

        
        for det in detections:

            if det["label"] != "person":
                continue

            x1, y1, x2, y2 = det["box"]
            w = x2 - x1
            h = y2 - y1

            dets.append(([x1, y1, w, h], det["confidence"], "person"))

        tracks = self.tracker.update_tracks(dets, frame=frame)

        results = []

        for track in tracks:

            if not track.is_confirmed():
                continue

            track_id = track.track_id
            l, t, r, b = map(int, track.to_ltrb())

            results.append({
                "id": track_id,
                "box": [l, t, r, b]
            })

        return results