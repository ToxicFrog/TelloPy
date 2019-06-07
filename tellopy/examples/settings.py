import os

# Filename format for images and videos.
IMG_FMT = os.getenv('HOME') + '/Pictures/tello-%Y-%m-%d_%H%M%S.jpeg'
VID_FMT = os.getenv('HOME') + '/Pictures/tello-%Y-%m-%d_%H%M%S.mp4'

# Set this to a filename to not connect to the drone and instead play the
# named file as the drone video stream, for testing purposes.
DRYRUN = False
# DRYRUN = "/tmp/tello-test.mp4"

# HUD configuration. Each entry is one line of the HUD.
# Entries are either a (format, key) pair, where the key is a field in the Tello
# FlightData object, or a (format, function) pair, where the function is passed
# the drone as its argument and returns the value to be formatted.
HUD = [
  ('ALT %3d', 'height'),
  ('SPD %3d', 'ground_speed'),
  ('BAT %3d%%', 'battery_percentage'),
  ('NET %3d%%', 'wifi_strength'),
  ('CAM %s', lambda drone: drone.zoom and "VID" or "PIC"),
]
