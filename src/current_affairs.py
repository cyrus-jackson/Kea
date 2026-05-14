import threading
import urllib.request
import urllib.error
import json

class CurrentAffairs:
    _shared_messages = []

    def __init__(self):
        self.messages = [
            "INITIALIZING NETWORK CONNECTION...",
            "WAITING FOR INCOMING TRANSMISSIONS..."
        ] + CurrentAffairs._shared_messages
        self.current_index = 0
        self.timer = 0.0
        self.display_duration = 60.0 # Seconds to display each message
        
        self.fetch_timer = 300.0 # Start high to force immediate fetch
        self.fetch_interval = 300.0 # 5 minutes (300 seconds)
        self.lock = threading.Lock()
        self.is_fetching = False

    def fetch_api_data(self):
        """Fetches random facts in a background thread so the main game loop doesn't freeze."""
        try:
            new_messages = []
            # Fetch 3 quirky facts
            for _ in range(3):
                req = urllib.request.Request(
                    "https://uselessfacts.jsph.pl/api/v2/facts/random", 
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    fact = data.get("text", "").upper()
                    if fact:
                        new_messages.append(fact)
            
            if new_messages:
                with self.lock:
                    self.messages = new_messages
                    self.current_index = 0
                    self.timer = 0.0 # reset display timer on new fetch
        except Exception as e:
            print("Failed to fetch facts:", e)
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
