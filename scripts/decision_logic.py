import logging
import os
import datetime

class RobotController:
    def __init__(self):
        # Setup logging
        log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'robot_decisions.log')
        
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger("RobotController")
        
        # To prevent spamming the logs, only log when the decision changes
        self.previous_decision = None

    def decide_action(self, detections):
        """
        Takes a list of object dictionaries (from the collision checker) and 
        returns the robot's next command.
        
        detections format: [{'class': 'person', 'status': 'DANGER', ...}, ...]
        """
        has_danger = False
        has_caution = False
        
        # Analyze the scene
        for det in detections:
            if det['status'] == "DANGER":
                has_danger = True
            elif det['status'] == "CAUTION":
                has_caution = True
                
        # Rule-based decision making
        if has_danger:
            decision = "STOP"
        elif has_caution:
            decision = "SLOW_DOWN"
        else:
            decision = "CONTINUE"
            
        # Log the decision if it changed
        if decision != self.previous_decision:
            self.logger.info(f"ACTION CHANGED TO: {decision}. Scene: {len(detections)} objects detected.")
            self.previous_decision = decision
            
        return decision
