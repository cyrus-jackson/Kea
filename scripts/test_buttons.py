import RPi.GPIO as GPIO
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description="Test a single hardware button.")
    parser.add_argument("--pin", type=int, default=26,
                        help="BCM GPIO pin to test (default: 26)")
    args = parser.parse_args()

    # Use BCM pin numbering
    GPIO.setmode(GPIO.BCM)
    
    print(f"Setting up button on BCM pin: {args.pin}")
    
    # Assuming the button is connected to ground, we use a pull-up resistor
    GPIO.setup(args.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"Pin {args.pin} initialized. Connected to ground (e.g., Physical Pin 39).")

    print("\nListening for button press... (Press Ctrl+C to exit)\n")

    # Track the previous state to only trigger on the initial press
    previous_state = GPIO.HIGH

    try:
        while True:
            current_state = GPIO.input(args.pin)
            
            # Button pressed when state changes from HIGH to LOW
            if current_state == GPIO.LOW and previous_state == GPIO.HIGH:
                print(f"Button on GPIO {args.pin} PRESSED!")
                # Basic debounce on press
                time.sleep(0.05)
            
            previous_state = current_state
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\nExiting and cleaning up GPIO...")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
