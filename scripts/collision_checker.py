import yaml
import os

class CollisionZoneChecker:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'configs', 'safety_params.yaml')
            
        with open(config_path, 'r') as file:
            self.params = yaml.safe_load(file)
            
        self.path_width = self.params.get('path_width_degrees', 15.0)
        self.danger_thresh = self.params.get('danger_distance_threshold', 4.0)
        self.caution_thresh = self.params.get('caution_distance_threshold', 7.0)

    def check_object(self, distance, angle):
        """
        Takes the distance and angle of an object and returns its safety status.
        Returns: 'SAFE', 'CAUTION', or 'DANGER'
        """
        # Check if object is outside the robot's physical path
        if abs(angle) > self.path_width:
            return "SAFE"
            
        # Object is IN the path, check distance
        # Because we used a relative metric where smaller = closer:
        if distance <= self.danger_thresh:
            return "DANGER"
        elif distance <= self.caution_thresh:
            return "CAUTION"
        else:
            return "SAFE"
