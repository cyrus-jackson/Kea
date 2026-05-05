class CurrentAffairs:
    def __init__(self):
        self.messages = ["BREAKING: UNREGISTERED AI DETECTED IN SECTOR 7",
            "TRAFFIC UPDATE: SKYWAY 4 BLOCKED DUE TO HOVER CAR COLLISION",
            "WEATHER ALERT: HEAVY ACID RAIN WARNING FOR LOWER LEVELS",
            "MEGACORP STOCKS REACH NEW HIGH OFF LATEST NEURAL IMPLANTS",
            "WANTED: CYBER HACKER 'GHOST' STILL AT LARGE",
            "UPCOMING: NEON RACING FINALS AT HIGH ORBIT STADIUM"
        ]
        self.current_index = 0
        self.timer = 0.0
        self.display_duration = 5.0 # Seconds to display each message

    def update(self, dt):
        """
        Updates the internal timer.
        Returns True if the message has changed, False otherwise.
        """
        self.timer += dt
        if self.timer >= self.display_duration:
            self.timer = 0.0
            self.current_index = (self.current_index + 1) % len(self.messages)
            return True
        return False

    def get_current_message(self):
        return self.messages[self.current_index]
