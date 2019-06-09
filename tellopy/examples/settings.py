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
# the drone and the client state as its argument and returns the value to be formatted.
HUD = [
  ('SPD %3d%%', lambda drone,state: state.speed),
  ('ALT %3d', 'height'),
  ('VEL %3d', 'ground_speed'),
  ('BAT %3d%%', 'battery_percentage'),
  ('NET %3d%%', 'wifi_strength'),
  ('CAM %s', lambda drone,state: drone.zoom and "VID" or "PIC"),
  ('%s', lambda drone,state: state.video_recorder and 'REC' or ''),
]

# Keymappings. Controller map is based on joystick_and_video.py.
# Controller button names are based on the xbox layout.
# TODO: The controller mappings don't do anything in keyboard_and_video yet.
CONTROLS = {
  # Moving around
  'forward':    ['w', 'YButton'],
  'backward':   ['s', 'AButton'],
  'left':       ['a', 'XButton'],
  'right':      ['d', 'BButton'],
  'up':         ['space', 'DPadUp'],
  'down':       ['left shift', 'right shift', 'DPadDown'],

  # Rotation
  'counter_clockwise':
                ['q', 'left', 'DPadLeft'],
  'clockwise':  ['e', 'right', 'DPadRight'],

  # Takeoff and landing
  'takeoff':    ['tab', 'R1'],
  'land':       ['backspace', 'L1'],
  'palm_land':  ['p'],

  # Video and photography
  'record':     ['r'],
  'zoom':       ['z'],
  'take_picture':
                ['enter', 'return'],

  # Client settings
  'help':       ['h'],
  'faster':     ['=', '+'],
  'slower':     ['-'],
  'exit':       ['escape'],

  # Direct axis-to-axis mappings for controllers.
  # Not implemented yet.
  # 'axis_throttle':  ['AxisLeftY'],
  # 'axis_pitch':     ['AxisRightY'],
  # 'axis_yaw':       ['AxisLeftX'],
  # 'axis_roll':      ['AxisRightX'],
}
