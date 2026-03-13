import cv2
import numpy as np

class MotionTracker:
    """
    Evaluates motion magnitude and direction using Lucas-Kanade Optical Flow.
    This replaces the heavy API-based Semantic Checker with a lightning-fast (1-2ms) local CV method.
    """
    def __init__(self):
        print("Initializing MotionTracker (Lucas-Kanade)...")

    def optical_flow_motion(self, prev_gray, curr_gray):
        """
        Calculates optical flow between two grayscale frames.
        Returns (magnitude, (direction_x, direction_y))
        """
        # Track corners between frames
        corners = cv2.goodFeaturesToTrack(prev_gray, 200, 0.01, 10)
        if corners is None:
            return 0.0, (0.0, 0.0)

        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray, curr_gray, corners, None
        )
        good_prev = corners[status == 1]
        good_next = next_pts[status == 1]

        if len(good_prev) == 0:
            return 0.0, (0.0, 0.0)

        # Flow vectors
        flow = good_next - good_prev
        magnitude = np.sqrt((flow**2).sum(axis=1))
        mean_flow = flow.mean(axis=0)           # Direction vector

        return float(magnitude.mean()), tuple(mean_flow.flatten())

    def interpret_direction(self, direction_tuple):
        """
        Converts the (dx, dy) direction vector into a human-readable motion string.
        """
        dx, dy = direction_tuple
        status = []
        
        # Thresholds to avoid micro-jitters
        if abs(dx) > 1.0:
            if dx > 0:
                status.append("Moving Right")
            else:
                status.append("Moving Left")
                
        if abs(dy) > 1.0:
            if dy > 0:
                status.append("Approaching") # Moving toward bottom usually means getting closer to camera in 3D space
            else:
                status.append("Moving Away")
                
        if not status:
            return "Static"
            
        return " & ".join(status)
