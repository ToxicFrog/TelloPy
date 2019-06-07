"""
tellopy sample using keyboard and video player

Requires mplayer to record/save video.


Controls:
- tab to lift off
- WASD to move the drone
- space/shift to ascend/descent slowly
- Q/E to yaw slowly
- arrow keys to ascend, descend, or yaw quickly
- backspace to land, or P to palm-land
- enter to take a picture
- R to start recording video, R again to stop recording
  (video and photos will be saved to a timestamped file in ~/Pictures/)
- Z to toggle camera zoom state
  (zoomed-in widescreen or high FOV 4:3)
"""

import time
import sys
import tellopy
import pygame
import pygame.display
import pygame.key
import pygame.locals
import pygame.font
import os
import datetime
import av
import threading
import numpy as np
# from tellopy import logger

from . import settings

# log = tellopy.logger.Logger('TelloUI')

prev_flight_data = None
video_recorder = None
font = None

def toggle_recording(drone, speed):
    global video_recorder
    if speed == 0:
        return

    if video_recorder:
        # already recording, so stop
        video_recorder.close()
        status_print('Video saved')
        video_recorder = None
        return
    else:
        # tell the frame handler to start a new recording
        video_recorder = datetime.datetime.now().strftime(settings.VID_FMT)
        status_print('Recording video to %s' % video_recorder)

def take_picture(drone, speed):
    if speed == 0:
        return
    drone.take_picture()

def palm_land(drone, speed):
    if speed == 0:
        return
    drone.palm_land()

def toggle_zoom(drone, speed):
    # In "video" mode the drone sends 1280x720 frames.
    # In "photo" mode it sends 2592x1936 (952x720) frames.
    # The video will always be centered in the window.
    # In photo mode, if we keep the window at 1280x720 that gives us ~160px on
    # each side for status information, which is ample.
    # Video mode is harder because then we need to abandon the 16:9 display size
    # if we want to put the HUD next to the video.
    if speed == 0:
        return
    drone.set_video_mode(not drone.zoom)
    pygame.display.get_surface().fill((0,0,0))
    pygame.display.flip()

help_mode = False
help_screen = None
def toggle_help(drone, speed):
    global help_mode, help_screen
    if speed == 0:
        pygame.display.get_surface().fill((0,0,0))
        pygame.display.flip()
        help_mode = False
    else:
        blitScaled(pygame.display.get_surface(), help_screen)
        pygame.display.flip()
        help_mode = True

controls = {
    'w': 'forward',
    's': 'backward',
    'a': 'left',
    'd': 'right',
    'space': 'up',
    'left shift': 'down',
    'right shift': 'down',
    'q': 'counter_clockwise',
    'e': 'clockwise',
    # arrow keys for fast turns and altitude adjustments
    'left': lambda drone, speed: drone.counter_clockwise(speed*2),
    'right': lambda drone, speed: drone.clockwise(speed*2),
    'up': lambda drone, speed: drone.up(speed*2),
    'down': lambda drone, speed: drone.down(speed*2),
    'tab': lambda drone, speed: drone.takeoff(),
    'backspace': lambda drone, speed: drone.land(),
    'p': palm_land,
    'r': toggle_recording,
    'z': toggle_zoom,
    'enter': take_picture,
    'return': take_picture,
    'h': toggle_help,
}

class FlightDataDisplay(object):
    # previous flight data value and surface to overlay
    _value = None
    _surface = None
    # function (drone, data) => new value
    # default is lambda drone,data: getattr(data, self._key)
    _update = None
    def __init__(self, key, format, colour=(255,255,255), update=None):
        self._key = key
        self._format = format
        self._colour = colour

        if update:
            self._update = update
        else:
            self._update = lambda drone,data: getattr(data, self._key)

    def update(self, drone, data):
        new_value = self._update(drone, data)
        if self._value != new_value:
            self._value = new_value
            self._surface = font.render(self._format % (new_value,), True, self._colour)
        return self._surface

def flight_data_mode(drone, *args):
    return (drone.zoom and "VID" or "PIC")

def flight_data_recording(*args):
    return (video_recorder and "REC 00:00" or "")  # TODO: duration of recording

def update_hud(hud, drone, flight_data):
    global help_mode
    if help_mode:
        return
    (w,h) = (158,0) # width available on side of screen in 4:3 mode
    blits = []
    for element in hud:
        surface = element.update(drone, flight_data)
        if surface is None:
            continue
        blits += [(surface, (0, h))]
        # w = max(w, surface.get_width())
        h += surface.get_height()
    h += 64  # add some padding
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    # overlay.fill((0,0,0)) # remove for mplayer overlay mode
    for blit in blits:
        overlay.blit(*blit)
    pygame.display.get_surface().blit(overlay, (0,0))
    # pygame.display.update(overlay.get_rect())

def status_print(text):
    pygame.display.set_caption(text)

hud = [
    FlightDataDisplay('height', 'ALT %3d'),
    FlightDataDisplay('ground_speed', 'SPD %3d'),
    FlightDataDisplay('battery_percentage', 'BAT %3d%%'),
    FlightDataDisplay('wifi_strength', 'NET %3d%%'),
    FlightDataDisplay(None, 'CAM %s', update=flight_data_mode),
    FlightDataDisplay(None, '%s', colour=(255, 0, 0), update=flight_data_recording),
]

def flightDataHandler(event, sender, data):
    global prev_flight_data
    text = str(data)
    if prev_flight_data != text:
        update_hud(hud, sender, data)
        prev_flight_data = text

def aspectScale(surface, dimensions):
    dw,dh = dimensions  # destination dims
    ow,oh = surface.get_size()  # original dims
    sx,sy = (dw/ow, dh/oh)  # scale factors
    return pygame.transform.smoothscale(surface, (int(ow*min(sx,sy)), int(oh*min(sx,sy))))

def blitScaled(dst, src):
    """Scale src to the size of dst, preserving aspect ratio, and blit it centered to dst."""
    dst_size = dst.get_size()
    src = aspectScale(src, dst_size)
    src_size = src.get_size()
    x = int((dst_size[0]-src_size[0])/2)
    y = int((dst_size[1]-src_size[1])/2)
    dst.blit(src, (x,y))

def sleepUntil(when):
    time.sleep(max(0, when - time.monotonic()))

def videoStreamThread(drone, screen):
    global video_recorder
    if settings.DRYRUN:
        container = av.open(settings.DRYRUN)
    else:
        container = av.open(drone.get_video_stream())
    resolution = screen.get_size()
    for packet in container.demux(video=0):
        for frame in packet.decode():
            surface = pygame.surfarray.make_surface(np.swapaxes(frame.to_rgb().to_ndarray(), 0, 1))
            blitScaled(screen, surface)
            # TODO: update OSD here
        if type(video_recorder) is str:
            video_recorder = av.open(video_recorder, 'w')
            video_recorder.add_stream(template=container.streams[0])
        if video_recorder:
            # FIXME: this results in a video with ~12,800fps rather than 30fps,
            # so you can't play it back unless you manually tell the player
            # to use 30fps.
            packet.stream = video_recorder.streams[0]
            video_recorder.mux_one(packet)

def handleFileReceived(event, sender, data):
    # Create a file in ~/Pictures/ to receive image data from the drone.
    path = datetime.datetime.now().strftime(settings.IMG_FMT)
    with open(path, 'wb') as fd:
        fd.write(data)
    status_print('Saved photo to %s' % path)

def main():
    pygame.init()
    pygame.display.init()
    if pygame.display.Info().wm:
        pygame.display.set_mode((1280,720))
    else:
        pygame.display.set_mode((0,0), pygame.FULLSCREEN)
    pygame.font.init()

    global font
    font = pygame.font.SysFont("dejavusansmono", 32)

    status_print('TelloPy Help')
    global help_screen
    help_screen = pygame.image.load("tellopy/examples/help.png")
    blitScaled(pygame.display.get_surface(), help_screen)
    pygame.display.flip()
    while True:
        e = pygame.event.wait()
        if e.type == pygame.locals.KEYUP:
            break

    status_print('TelloPy')
    pygame.display.get_surface().fill((0,0,0))
    pygame.display.flip()

    speed = 30
    drone = tellopy.Tello()
    drone.connect()
    if not settings.DRYRUN:
        drone.start_video()
        drone.subscribe(drone.EVENT_FLIGHT_DATA, flightDataHandler)
        drone.subscribe(drone.EVENT_FILE_RECEIVED, handleFileReceived)

    framebuffer = pygame.display.get_surface().copy()
    threading.Thread(target=videoStreamThread, args=[drone, framebuffer]).start()

    try:
        while 1:
            if not help_mode:
                pygame.display.get_surface().blit(framebuffer, (0,0))
                pygame.display.flip()
            time.sleep(0.01)  # loop with pygame.event.get() is too mush tight w/o some sleep
            for e in pygame.event.get():
                # WASD for movement
                if e.type == pygame.locals.KEYDOWN:
                    keyname = pygame.key.name(e.key)
                    print('+' + keyname)
                    if keyname == 'escape':
                        drone.quit()
                        os._exit(0)
                    if keyname in controls:
                        key_handler = controls[keyname]
                        if type(key_handler) == str:
                            getattr(drone, key_handler)(speed)
                        else:
                            key_handler(drone, speed)

                elif e.type == pygame.locals.KEYUP:
                    keyname = pygame.key.name(e.key)
                    print('-' + keyname)
                    if keyname in controls:
                        key_handler = controls[keyname]
                        if type(key_handler) == str:
                            getattr(drone, key_handler)(0)
                        else:
                            key_handler(drone, 0)
    except Exception as e:
        import traceback
        traceback.print_exception(*sys.exc_info())
    finally:
        print('Shutting down connection to drone...')
        if video_recorder:
            toggle_recording(drone, 1)
        drone.quit()
        exit(1)

if __name__ == '__main__':
    main()
