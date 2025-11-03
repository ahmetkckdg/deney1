from gaze_tracking import GazeTracking
import cv2

class EyeTracker:
    def __init__(self):
        self.gaze = GazeTracking()
        self.webcam = cv2.VideoCapture(0)

    def get_gaze_data(self):
        _, frame = self.webcam.read()
        self.gaze.refresh(frame)
        horizontal = self.gaze.horizontal_ratio()
        vertical = self.gaze.vertical_ratio()
        return (horizontal, vertical)

    def release(self):
        self.webcam.release()
        cv2.destroyAllWindows()