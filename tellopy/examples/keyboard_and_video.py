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
from functools import partial
from . import settings

# log = tellopy.logger.Logger('TelloUI')

# Set up the control mappings.
# settings.CONTROLS is a map[command name => list of key or button bindings]
# We reverse that and produce a map[key or button => command function].
def setupKeyMap():
    keymap = {}
    for command,bindings in settings.CONTROLS.items():
        for binding in bindings:
            try:
                keymap['+' + binding] = globals()["command_%s" % command]
            except KeyError:
                print('Error setting up control mappings: "+%s" was bound to "%s" but no handler exists for that command' % (binding, command))
                sys.exit(1)
            try:
                keymap['-' + binding] = globals()["command_%s_off" % command]
            except KeyError:
                # binding keyup isn't mandatory
                pass

    return keymap

#### Command implementations ####

# Command handlers all have the name command_foo (called on key down) or
# command_foo_off (called on key up).
# If one of these is missing it's simply not called.

# Set up the command handlers for simple methods on the drone that just take
# 'speed' as their sole argument, with 0 meaning to stop doing the thing.
# The use of partial() here is necessary because if we just use `command` in the
# lambda body without making it an argument, all of the handlers will close over
# the same binding of `command` and will end up implementing whatever value
# `command` had last (in this case take_picture from the second loop below).
for command in ['forward', 'backward', 'left', 'right', 'up', 'down',
                'counter_clockwise', 'clockwise']:
    locals()["command_%s" % command] = partial(
        lambda command,drone,state: getattr(drone, command)(state.speed), command)
    locals()["command_%s_off" % command] = partial(
        lambda command,drone,state: getattr(drone, command)(0), command)

# Command handlers for methods on the drone that take no arguments.
for command in ['takeoff', 'land', 'palm_land', 'take_picture']:
    locals()["command_%s" % command] = partial(
        lambda command,drone,_: getattr(drone, command)(), command)

# Command handlers that require special handling on the client.

def command_faster(drone, state):
    state.speed = min(100, state.speed + 10)

def command_slower(drone, state):
    state.speed = max(0, state.speed - 10)

def command_record(drone, state):
    if state.video_recorder:
        # already recording, so stop
        state.video_recorder.close()
        status_print('Video saved to %s' % state.video_name)
        state.video_recorder = None
        state.video_name = None
        return
    else:
        # tell the frame handler to start a new recording
        state.video_name = datetime.datetime.now().strftime(settings.VID_FMT)
        status_print('Recording video to %s' % state.video_name)

def command_zoom(drone, state):
    # In "video" mode the drone sends 1280x720 frames.
    # In "photo" mode it sends 2592x1936 (952x720) frames.
    drone.set_video_mode(not drone.zoom)
    state.framebuffer.fill((0,0,0))

def command_help(drone, state):
    # Enabling help_mode takes over the rendering loop, so we don't need to
    # worry about the framebuffer and can just write directly to the screen.
    blitScaled(pygame.display.get_surface(), state.help_screen)
    pygame.display.flip()
    state.help_mode = True

def command_help_off(drone, state):
    state.help_mode = False

def command_exit(drone, state):
    drone.quit()
    os._exit(0)

def render_hud(drone, state):
    """Renders the HUD to a pygame surface and returns it."""
    lines = []
    width,height = 0,0
    for fmt,key in settings.HUD:
        if type(key) is str:
            value = fmt % getattr(drone.flight_data, key)
        else:
            value = fmt % key(drone, state)
        surface = state.font.render(value, True, (255,255,255))
        width = max(width, surface.get_width())
        height += surface.get_height()
        lines += [surface]
    # Blit everything onto the final surface.
    y = 0
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    surface.fill((0,0,0))
    for line in lines:
        surface.blit(line, (0, y))
        y += line.get_height()
    return surface

def status_print(text):
    pygame.display.set_caption(text)

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

def videoStreamThread(drone, state):
    if settings.DRYRUN:
        container = av.open(settings.DRYRUN)
    else:
        container = av.open(drone.get_video_stream())
    screen = state.framebuffer
    resolution = screen.get_size()
    for packet in container.demux(video=0):
        for frame in packet.decode():
            surface = pygame.surfarray.make_surface(np.swapaxes(frame.to_rgb().to_ndarray(), 0, 1))
            blitScaled(screen, surface)
            screen.blit(render_hud(drone, state), (0,0))
        if state.video_name and not state.video_recorder:
            # We've been asked to start recording video.
            state.video_recorder = av.open(state.video_name, 'w')
            state.video_recorder.add_stream(template=container.streams[0])
        if state.video_recorder:
            # FIXME: this results in a video with ~12,800fps rather than 30fps,
            # so you can't play it back unless you manually tell the player
            # to use 30fps.
            # FIXME: there's a race condition here where the key event handler
            # might close the stream and unset state.video_recorder in between
            # the if and the call to mux_one, causing a crash.
            packet.stream = state.video_recorder.streams[0]
            state.video_recorder.mux_one(packet)

def handleFileReceived(event, sender, data):
    # Create a file in ~/Pictures/ to receive image data from the drone.
    path = datetime.datetime.now().strftime(settings.IMG_FMT)
    with open(path, 'wb') as fd:
        fd.write(data)
    status_print('Saved photo to %s' % path)

class ClientState:
    video_recorder = None
    video_name = None
    font = None
    speed = 30
    help_mode = False
    help_screen = None
    framebuffer = None

def main():
    keymap = setupKeyMap()
    state = ClientState()

    pygame.init()
    pygame.display.init()
    if pygame.display.Info().wm:
        pygame.display.set_mode((1280,720))
    else:
        pygame.display.set_mode((0,0), pygame.FULLSCREEN)
    pygame.font.init()

    state.font = pygame.font.SysFont("dejavusansmono", 32)
    state.help_screen = pygame.image.load("tellopy/examples/help.png")

    blitScaled(pygame.display.get_surface(), state.help_screen)
    pygame.display.flip()
    while True:
        e = pygame.event.wait()
        if e.type == pygame.locals.KEYUP:
            break

    status_print('TelloPy')
    pygame.display.get_surface().fill((0,0,0))
    pygame.display.flip()

    drone = tellopy.Tello()
    drone.connect()
    if not settings.DRYRUN:
        drone.start_video()
        drone.subscribe(drone.EVENT_FILE_RECEIVED, handleFileReceived)

    state.framebuffer = pygame.display.get_surface().copy()
    threading.Thread(target=videoStreamThread, args=[drone, state]).start()

    try:
        while 1:
            if not state.help_mode:
                pygame.display.get_surface().blit(state.framebuffer, (0,0))
                pygame.display.flip()
            time.sleep(0.01)  # loop with pygame.event.get() is too mush tight w/o some sleep
            for e in pygame.event.get():
                if e.type == pygame.locals.KEYDOWN:
                    keyname = '+' + pygame.key.name(e.key)
                    try:
                        keymap[keyname](drone, state)
                    except KeyError:
                        pass
                elif e.type == pygame.locals.KEYUP:
                    keyname = '-' + pygame.key.name(e.key)
                    try:
                        keymap[keyname](drone, state)
                    except KeyError:
                        pass
    except Exception as e:
        import traceback
        traceback.print_exception(*sys.exc_info())
    finally:
        print('Shutting down connection to drone...')
        if state.video_recorder:
            command_record(drone, state)
        drone.quit()
        exit(1)

if __name__ == '__main__':
    main()
