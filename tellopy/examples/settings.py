import os

# Filename format for images and videos.
IMG_FMT = os.getenv('HOME') + '/Pictures/tello-%Y-%m-%d_%H%M%S.jpeg'
VID_FMT = os.getenv('HOME') + '/Pictures/tello-%Y-%m-%d_%H%M%S.mp4'

# Set this to a filename to not connect to the drone and instead play the
# named file as the drone video stream, for testing purposes.
DRYRUN = False
# DRYRUN = "/tmp/tello-test.mp4"

