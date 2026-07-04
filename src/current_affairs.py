import threading

from system_protocol import SystemProtocol


class CurrentAffairs:
    _shared_messages = []
    _protocol = SystemProtocol()

    def __init__(self):
        self.messages = [
            "SYSTEM PROTOCOL ONLINE.",
            CurrentAffairs._protocol.next_message(),
        ] + CurrentAffairs._shared_messages
        self.current_index = 0
        self.timer = 0.0
        self.display_duration = 60.0 # Seconds to display each message
        
        self.fetch_timer = 300.0 # Start high to force immediate fetch
        self.fetch_interval = 300.0 # 5 minutes (300 seconds)
        self.lock = threading.Lock()
        self.is_fetching = False

    def fetch_api_data(self):
        """Refill the rotation from the local SystemProtocol engine
        (kept on the background thread to preserve the old call shape)."""
        try:
            new_messages = CurrentAffairs._protocol.next_messages(3)
            if new_messages:
                with self.lock:
                    self.messages = new_messages
                    self.current_index = 0
                    self.timer = 0.0  # reset display timer on refresh
        except Exception as e:
            print("Failed to generate protocol messages:", e)
        finally:
            self.is_fetching = False

    def update(self, dt):
        """
        Updates the internal timer.
        Returns True if the message has changed, False otherwise.
        """
        self.timer += dt
        self.fetch_timer += dt
        
        # Trigger background fetch if interval reached
        if self.fetch_timer >= self.fetch_interval and not self.is_fetching:
            self.fetch_timer = 0.0
            self.is_fetching = True
            threading.Thread(target=self.fetch_api_data, daemon=True).start()

        # Handle display message rotation
        if self.timer >= self.display_duration:
            self.timer = 0.0
            with self.lock:
                if len(self.messages) > 0:
                    self.current_index = (self.current_index + 1) % len(self.messages)
            return True
        
        return False

    def get_current_message(self):
        with self.lock:
            if not self.messages:
                return ""
            if self.current_index >= len(self.messages):
                self.current_index = 0
            return self.messages[self.current_index]

    def add_important_message(self, message):
        """Insert a high-priority message to the current affairs rotation immediately."""
        with self.lock:
            if message not in CurrentAffairs._shared_messages:
                CurrentAffairs._shared_messages.append(message)
            # We add it right next in the rotation to be shown quickly
            if self.messages:
                insert_idx = (self.current_index + 1) % len(self.messages)
                self.messages.insert(insert_idx, message)
            else:
                self.messages.append(message)
                self.current_index = 0
