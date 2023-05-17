#!/usr/bin/env python3

import os, sys, ctypes, ctypes.util, logging, mmap, struct, getopt, select
from fcntl import ioctl
from threading import Thread

from cameractrls import v4l2_capability, v4l2_format, v4l2_requestbuffers, v4l2_buffer
from cameractrls import VIDIOC_QUERYCAP, VIDIOC_G_FMT, VIDIOC_S_FMT, VIDIOC_REQBUFS, VIDIOC_QUERYBUF, VIDIOC_QBUF, VIDIOC_DQBUF, VIDIOC_STREAMON, VIDIOC_STREAMOFF
from cameractrls import V4L2_CAP_VIDEO_CAPTURE, V4L2_CAP_STREAMING, V4L2_MEMORY_MMAP, V4L2_BUF_TYPE_VIDEO_CAPTURE
from cameractrls import V4L2_PIX_FMT_YUYV, V4L2_PIX_FMT_YVYU, V4L2_PIX_FMT_UYVY, V4L2_PIX_FMT_YU12, V4L2_PIX_FMT_YV12
from cameractrls import V4L2_PIX_FMT_NV12, V4L2_PIX_FMT_NV21, V4L2_PIX_FMT_GREY
from cameractrls import V4L2_PIX_FMT_RGB565, V4L2_PIX_FMT_RGB24, V4L2_PIX_FMT_BGR24, V4L2_PIX_FMT_RX24
from cameractrls import V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG

sdl2lib = ctypes.util.find_library('SDL2-2.0')
if sdl2lib == None:
    print('libSDL2 not found, please install the libsdl2-2.0 package!')
    sys.exit(2)
sdl2 = ctypes.CDLL(sdl2lib)

turbojpeglib = ctypes.util.find_library('turbojpeg')
if turbojpeglib == None:
    print('libturbojpeg not found, please install the libturbojpeg package!')
    sys.exit(2)
turbojpeg = ctypes.CDLL(turbojpeglib)

class SDL_PixelFormat(ctypes.Structure):
    _fields_ = [
        ('format', ctypes.c_uint32),
        ('palette', ctypes.c_void_p),
    ]

class SDL_Surface(ctypes.Structure):
    _fields_ = [
        ('flags', ctypes.c_uint32),
        ('format', ctypes.POINTER(SDL_PixelFormat)),
        ('w', ctypes.c_int),
        ('h', ctypes.c_int),
        ('pitch', ctypes.c_int),
        ('pixels', ctypes.c_void_p),
    ]

SDL_Init = sdl2.SDL_Init
SDL_Init.restype = ctypes.c_int
SDL_Init.argtypes = [ctypes.c_uint32]
# int SDL_Init(Uint32 flags);

SDL_GetError = sdl2.SDL_GetError
SDL_GetError.restype = ctypes.c_char_p
SDL_GetError.argtypes = []
# const char* SDL_GetError(void);

SDL_RegisterEvents = sdl2.SDL_RegisterEvents
SDL_RegisterEvents.restype = ctypes.c_uint32
SDL_RegisterEvents.argtypes = [ctypes.c_int]
# Uint32 SDL_RegisterEvents(int numevents);

SDL_CreateWindow = sdl2.SDL_CreateWindow
SDL_CreateWindow.restype = ctypes.c_void_p
SDL_CreateWindow.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
# SDL_Window * SDL_CreateWindow(const char *title, int x, int y, int w, int h, Uint32 flags);

SDL_CreateRenderer = sdl2.SDL_CreateRenderer
SDL_CreateRenderer.restype = ctypes.c_void_p
SDL_CreateRenderer.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
# SDL_Renderer * SDL_CreateRenderer(SDL_Window * window, int index, Uint32 flags);

SDL_RenderSetLogicalSize = sdl2.SDL_RenderSetLogicalSize
SDL_RenderSetLogicalSize.restype = ctypes.c_int
SDL_RenderSetLogicalSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
# int SDL_RenderSetLogicalSize(SDL_Renderer * renderer, int w, int h);

SDL_CreateTexture = sdl2.SDL_CreateTexture
SDL_CreateTexture.restype = ctypes.c_void_p
SDL_CreateTexture.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_int, ctypes.c_int]
# SDL_Texture * SDL_CreateTexture(SDL_Renderer * renderer, Uint32 format, int access, int w, int h);

SDL_UpdateTexture = sdl2.SDL_UpdateTexture
SDL_UpdateTexture.restype = ctypes.c_int
SDL_UpdateTexture.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
# int SDL_UpdateTexture(SDL_Texture * texture, const SDL_Rect * rect, const void *pixels, int pitch);

SDL_RenderClear = sdl2.SDL_RenderClear
SDL_RenderClear.restype = ctypes.c_int
SDL_RenderClear.argtypes = [ctypes.c_void_p]
# int SDL_RenderClear(SDL_Renderer * renderer);

SDL_RenderCopyEx = sdl2.SDL_RenderCopyEx
SDL_RenderCopyEx.restype = ctypes.c_int
SDL_RenderCopyEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_double, ctypes.c_void_p, ctypes.c_int]
#int SDL_RenderCopyEx(SDL_Renderer * renderer, SDL_Texture * texture, const SDL_Rect * srcrect, const SDL_Rect * dstrect,
#                   const double angle, const SDL_Point *center, const SDL_RendererFlip flip);

SDL_CreateRGBSurfaceFrom = sdl2.SDL_CreateRGBSurfaceFrom
SDL_CreateRGBSurfaceFrom.restype = ctypes.POINTER(SDL_Surface)
SDL_CreateRGBSurfaceFrom.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
#SDL_Surface* SDL_CreateRGBSurfaceFrom(void *pixels, int width, int height, int depth, int pitch,
# Uint32 Rmask, Uint32 Gmask, Uint32 Bmask, Uint32 Amask);

SDL_SetPaletteColors = sdl2.SDL_SetPaletteColors
SDL_SetPaletteColors.restype = ctypes.c_int
SDL_SetPaletteColors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
#int SDL_SetPaletteColors(SDL_Palette * palette, const SDL_Color * colors, int firstcolor, int ncolors);

SDL_CreateTextureFromSurface = sdl2.SDL_CreateTextureFromSurface
SDL_CreateTextureFromSurface.restype = ctypes.c_void_p
SDL_CreateTextureFromSurface.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
#SDL_Texture* SDL_CreateTextureFromSurface(SDL_Renderer * renderer, SDL_Surface * surface);

SDL_DestroyTexture = sdl2.SDL_DestroyTexture
SDL_DestroyTexture.restype = None
SDL_DestroyTexture.argtypes = [ctypes.c_void_p]
#void SDL_DestroyTexture(SDL_Texture * texture);

SDL_RenderPresent = sdl2.SDL_RenderPresent
SDL_RenderPresent.restype = None
SDL_RenderPresent.argtypes = [ctypes.c_void_p]
# void SDL_RenderPresent(SDL_Renderer * renderer);

SDL_PushEvent = sdl2.SDL_PushEvent
SDL_PushEvent.restype = ctypes.c_int
SDL_PushEvent.argtypes = [ctypes.c_void_p]
#int SDL_PushEvent(SDL_Event * event);

SDL_WaitEvent = sdl2.SDL_WaitEvent
SDL_WaitEvent.restype = ctypes.c_int
SDL_WaitEvent.argtypes = [ctypes.c_void_p]
# int SDL_WaitEvent(SDL_Event * event);

SDL_DestroyWindow = sdl2.SDL_DestroyWindow
SDL_DestroyWindow.argtypes = [ctypes.c_void_p]
# void SDL_DestroyWindow(SDL_Window * window);

SDL_Quit = sdl2.SDL_Quit
# void SDL_Quit(void);

SDL_SetWindowFullscreen = sdl2.SDL_SetWindowFullscreen
SDL_SetWindowFullscreen.restype = ctypes.c_int
SDL_SetWindowFullscreen.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
# int SDL_SetWindowFullscreen(SDL_Window * window, Uint32 flags);

SDL_ShowSimpleMessageBox = sdl2.SDL_ShowSimpleMessageBox
SDL_ShowSimpleMessageBox.restype = ctypes.c_int
SDL_ShowSimpleMessageBox.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
# int SDL_ShowSimpleMessageBox(Uint32 flags, const char *title, const char *message, SDL_Window *window);

SDL_INIT_VIDEO = 0x00000020
SDL_QUIT = 0x100
SDL_KEYDOWN = 0x300
SDL_MOUSEBUTTONUP = 0x402
SDL_BUTTON_LEFT = 1
SDLK_c = ord('c')
SDLK_f = ord('f')
SDLK_m = ord('m')
SDLK_q = ord('q')
SDLK_r = ord('r')
SDLK_ESCAPE = 27
KMOD_NONE = 0x0000
KMOD_LSHIFT = 0x0001
KMOD_RSHIFT = 0x0002
KMOD_SHIFT = KMOD_LSHIFT | KMOD_RSHIFT


SDL_PAL_GRAYSCALE_L = b'\
\x00\x00\x00\0\x01\x01\x01\0\x02\x02\x02\0\x03\x03\x03\0\x04\x04\x04\0\x05\x05\x05\0\x06\x06\x06\0\x07\x07\x07\0\x08\x08\x08\0\x09\x09\x09\0\x0a\x0a\x0a\0\
\x0b\x0b\x0b\0\x0c\x0c\x0c\0\x0d\x0d\x0d\0\x0e\x0e\x0e\0\x0f\x0f\x0f\0\x10\x10\x10\0\x11\x11\x11\0\x12\x12\x12\0\x13\x13\x13\0\x14\x14\x14\0\x15\x15\x15\0\
\x16\x16\x16\0\x17\x17\x17\0\x18\x18\x18\0\x19\x19\x19\0\x1a\x1a\x1a\0\x1b\x1b\x1b\0\x1c\x1c\x1c\0\x1d\x1d\x1d\0\x1e\x1e\x1e\0\x1f\x1f\x1f\0\x20\x20\x20\0\
\x21\x21\x21\0\x22\x22\x22\0\x23\x23\x23\0\x24\x24\x24\0\x25\x25\x25\0\x26\x26\x26\0\x27\x27\x27\0\x28\x28\x28\0\x29\x29\x29\0\x2a\x2a\x2a\0\x2b\x2b\x2b\0\
\x2c\x2c\x2c\0\x2d\x2d\x2d\0\x2e\x2e\x2e\0\x2f\x2f\x2f\0\x30\x30\x30\0\x31\x31\x31\0\x32\x32\x32\0\x33\x33\x33\0\x34\x34\x34\0\x35\x35\x35\0\x36\x36\x36\0\
\x37\x37\x37\0\x38\x38\x38\0\x39\x39\x39\0\x3a\x3a\x3a\0\x3b\x3b\x3b\0\x3c\x3c\x3c\0\x3d\x3d\x3d\0\x3e\x3e\x3e\0\x3f\x3f\x3f\0\x40\x40\x40\0\x41\x41\x41\0\
\x42\x42\x42\0\x43\x43\x43\0\x44\x44\x44\0\x45\x45\x45\0\x46\x46\x46\0\x47\x47\x47\0\x48\x48\x48\0\x49\x49\x49\0\x4a\x4a\x4a\0\x4b\x4b\x4b\0\x4c\x4c\x4c\0\
\x4d\x4d\x4d\0\x4e\x4e\x4e\0\x4f\x4f\x4f\0\x50\x50\x50\0\x51\x51\x51\0\x52\x52\x52\0\x53\x53\x53\0\x54\x54\x54\0\x55\x55\x55\0\x56\x56\x56\0\x57\x57\x57\0\
\x58\x58\x58\0\x59\x59\x59\0\x5a\x5a\x5a\0\x5b\x5b\x5b\0\x5c\x5c\x5c\0\x5d\x5d\x5d\0\x5e\x5e\x5e\0\x5f\x5f\x5f\0\x60\x60\x60\0\x61\x61\x61\0\x62\x62\x62\0\
\x63\x63\x63\0\x64\x64\x64\0\x65\x65\x65\0\x66\x66\x66\0\x67\x67\x67\0\x68\x68\x68\0\x69\x69\x69\0\x6a\x6a\x6a\0\x6b\x6b\x6b\0\x6c\x6c\x6c\0\x6d\x6d\x6d\0\
\x6e\x6e\x6e\0\x6f\x6f\x6f\0\x70\x70\x70\0\x71\x71\x71\0\x72\x72\x72\0\x73\x73\x73\0\x74\x74\x74\0\x75\x75\x75\0\x76\x76\x76\0\x77\x77\x77\0\x78\x78\x78\0\
\x79\x79\x79\0\x7a\x7a\x7a\0\x7b\x7b\x7b\0\x7c\x7c\x7c\0\x7d\x7d\x7d\0\x7e\x7e\x7e\0\x7f\x7f\x7f\0\x80\x80\x80\0\x81\x81\x81\0\x82\x82\x82\0\x83\x83\x83\0\
\x84\x84\x84\0\x85\x85\x85\0\x86\x86\x86\0\x87\x87\x87\0\x88\x88\x88\0\x89\x89\x89\0\x8a\x8a\x8a\0\x8b\x8b\x8b\0\x8c\x8c\x8c\0\x8d\x8d\x8d\0\x8e\x8e\x8e\0\
\x8f\x8f\x8f\0\x90\x90\x90\0\x91\x91\x91\0\x92\x92\x92\0\x93\x93\x93\0\x94\x94\x94\0\x95\x95\x95\0\x96\x96\x96\0\x97\x97\x97\0\x98\x98\x98\0\x99\x99\x99\0\
\x9a\x9a\x9a\0\x9b\x9b\x9b\0\x9c\x9c\x9c\0\x9d\x9d\x9d\0\x9e\x9e\x9e\0\x9f\x9f\x9f\0\xa0\xa0\xa0\0\xa1\xa1\xa1\0\xa2\xa2\xa2\0\xa3\xa3\xa3\0\xa4\xa4\xa4\0\
\xa5\xa5\xa5\0\xa6\xa6\xa6\0\xa7\xa7\xa7\0\xa8\xa8\xa8\0\xa9\xa9\xa9\0\xaa\xaa\xaa\0\xab\xab\xab\0\xac\xac\xac\0\xad\xad\xad\0\xae\xae\xae\0\xaf\xaf\xaf\0\
\xb0\xb0\xb0\0\xb1\xb1\xb1\0\xb2\xb2\xb2\0\xb3\xb3\xb3\0\xb4\xb4\xb4\0\xb5\xb5\xb5\0\xb6\xb6\xb6\0\xb7\xb7\xb7\0\xb8\xb8\xb8\0\xb9\xb9\xb9\0\xba\xba\xba\0\
\xbb\xbb\xbb\0\xbc\xbc\xbc\0\xbd\xbd\xbd\0\xbe\xbe\xbe\0\xbf\xbf\xbf\0\xc0\xc0\xc0\0\xc1\xc1\xc1\0\xc2\xc2\xc2\0\xc3\xc3\xc3\0\xc4\xc4\xc4\0\xc5\xc5\xc5\0\
\xc6\xc6\xc6\0\xc7\xc7\xc7\0\xc8\xc8\xc8\0\xc9\xc9\xc9\0\xca\xca\xca\0\xcb\xcb\xcb\0\xcc\xcc\xcc\0\xcd\xcd\xcd\0\xce\xce\xce\0\xcf\xcf\xcf\0\xd0\xd0\xd0\0\
\xd1\xd1\xd1\0\xd2\xd2\xd2\0\xd3\xd3\xd3\0\xd4\xd4\xd4\0\xd5\xd5\xd5\0\xd6\xd6\xd6\0\xd7\xd7\xd7\0\xd8\xd8\xd8\0\xd9\xd9\xd9\0\xda\xda\xda\0\xdb\xdb\xdb\0\
\xdc\xdc\xdc\0\xdd\xdd\xdd\0\xde\xde\xde\0\xdf\xdf\xdf\0\xe0\xe0\xe0\0\xe1\xe1\xe1\0\xe2\xe2\xe2\0\xe3\xe3\xe3\0\xe4\xe4\xe4\0\xe5\xe5\xe5\0\xe6\xe6\xe6\0\
\xe7\xe7\xe7\0\xe8\xe8\xe8\0\xe9\xe9\xe9\0\xea\xea\xea\0\xeb\xeb\xeb\0\xec\xec\xec\0\xed\xed\xed\0\xee\xee\xee\0\xef\xef\xef\0\xf0\xf0\xf0\0\xf1\xf1\xf1\0\
\xf2\xf2\xf2\0\xf3\xf3\xf3\0\xf4\xf4\xf4\0\xf5\xf5\xf5\0\xf6\xf6\xf6\0\xf7\xf7\xf7\0\xf8\xf8\xf8\0\xf9\xf9\xf9\0\xfa\xfa\xfa\0\xfb\xfb\xfb\0\xfc\xfc\xfc\0\
\xfd\xfd\xfd\0\xfe\xfe\xfe\0\xff\xff\xff\0'
SDL_PAL_GRAYSCALE = (ctypes.c_uint8 * len(SDL_PAL_GRAYSCALE_L))(*SDL_PAL_GRAYSCALE_L)

# palette from https://github.com/sciapp/gr/blob/master/lib/gr/cm.h
SDL_PAL_INFERNO_L = b'\
\x00\x00\x04\0\x01\x00\x05\0\x01\x01\x06\0\x01\x01\x08\0\x02\x01\x0a\0\x02\x02\x0c\0\x02\x02\x0e\0\x03\x02\x10\0\x04\x03\x12\0\x04\x03\x14\0\x05\x04\x17\0\
\x06\x04\x19\0\x07\x05\x1b\0\x08\x05\x1d\0\x09\x06\x1f\0\x0a\x07\x22\0\x0b\x07\x24\0\x0c\x08\x26\0\x0d\x08\x29\0\x0e\x09\x2b\0\x10\x09\x2d\0\x11\x0a\x30\0\
\x12\x0a\x32\0\x14\x0b\x34\0\x15\x0b\x37\0\x16\x0b\x39\0\x18\x0c\x3c\0\x19\x0c\x3e\0\x1b\x0c\x41\0\x1c\x0c\x43\0\x1e\x0c\x45\0\x1f\x0c\x48\0\x21\x0c\x4a\0\
\x23\x0c\x4c\0\x24\x0c\x4f\0\x26\x0c\x51\0\x28\x0b\x53\0\x29\x0b\x55\0\x2b\x0b\x57\0\x2d\x0b\x59\0\x2f\x0a\x5b\0\x31\x0a\x5c\0\x32\x0a\x5e\0\x34\x0a\x5f\0\
\x36\x09\x61\0\x38\x09\x62\0\x39\x09\x63\0\x3b\x09\x64\0\x3d\x09\x65\0\x3e\x09\x66\0\x40\x0a\x67\0\x42\x0a\x68\0\x44\x0a\x68\0\x45\x0a\x69\0\x47\x0b\x6a\0\
\x49\x0b\x6a\0\x4a\x0c\x6b\0\x4c\x0c\x6b\0\x4d\x0d\x6c\0\x4f\x0d\x6c\0\x51\x0e\x6c\0\x52\x0e\x6d\0\x54\x0f\x6d\0\x55\x0f\x6d\0\x57\x10\x6e\0\x59\x10\x6e\0\
\x5a\x11\x6e\0\x5c\x12\x6e\0\x5d\x12\x6e\0\x5f\x13\x6e\0\x61\x13\x6e\0\x62\x14\x6e\0\x64\x15\x6e\0\x65\x15\x6e\0\x67\x16\x6e\0\x69\x16\x6e\0\x6a\x17\x6e\0\
\x6c\x18\x6e\0\x6d\x18\x6e\0\x6f\x19\x6e\0\x71\x19\x6e\0\x72\x1a\x6e\0\x74\x1a\x6e\0\x75\x1b\x6e\0\x77\x1c\x6d\0\x78\x1c\x6d\0\x7a\x1d\x6d\0\x7c\x1d\x6d\0\
\x7d\x1e\x6d\0\x7f\x1e\x6c\0\x80\x1f\x6c\0\x82\x20\x6c\0\x84\x20\x6b\0\x85\x21\x6b\0\x87\x21\x6b\0\x88\x22\x6a\0\x8a\x22\x6a\0\x8c\x23\x69\0\x8d\x23\x69\0\
\x8f\x24\x69\0\x90\x25\x68\0\x92\x25\x68\0\x93\x26\x67\0\x95\x26\x67\0\x97\x27\x66\0\x98\x27\x66\0\x9a\x28\x65\0\x9b\x29\x64\0\x9d\x29\x64\0\x9f\x2a\x63\0\
\xa0\x2a\x63\0\xa2\x2b\x62\0\xa3\x2c\x61\0\xa5\x2c\x60\0\xa6\x2d\x60\0\xa8\x2e\x5f\0\xa9\x2e\x5e\0\xab\x2f\x5e\0\xad\x30\x5d\0\xae\x30\x5c\0\xb0\x31\x5b\0\
\xb1\x32\x5a\0\xb3\x32\x5a\0\xb4\x33\x59\0\xb6\x34\x58\0\xb7\x35\x57\0\xb9\x35\x56\0\xba\x36\x55\0\xbc\x37\x54\0\xbd\x38\x53\0\xbf\x39\x52\0\xc0\x3a\x51\0\
\xc1\x3a\x50\0\xc3\x3b\x4f\0\xc4\x3c\x4e\0\xc6\x3d\x4d\0\xc7\x3e\x4c\0\xc8\x3f\x4b\0\xca\x40\x4a\0\xcb\x41\x49\0\xcc\x42\x48\0\xce\x43\x47\0\xcf\x44\x46\0\
\xd0\x45\x45\0\xd2\x46\x44\0\xd3\x47\x43\0\xd4\x48\x42\0\xd5\x4a\x41\0\xd7\x4b\x3f\0\xd8\x4c\x3e\0\xd9\x4d\x3d\0\xda\x4e\x3c\0\xdb\x50\x3b\0\xdd\x51\x3a\0\
\xde\x52\x38\0\xdf\x53\x37\0\xe0\x55\x36\0\xe1\x56\x35\0\xe2\x57\x34\0\xe3\x59\x33\0\xe4\x5a\x31\0\xe5\x5c\x30\0\xe6\x5d\x2f\0\xe7\x5e\x2e\0\xe8\x60\x2d\0\
\xe9\x61\x2b\0\xea\x63\x2a\0\xeb\x64\x29\0\xeb\x66\x28\0\xec\x67\x26\0\xed\x69\x25\0\xee\x6a\x24\0\xef\x6c\x23\0\xef\x6e\x21\0\xf0\x6f\x20\0\xf1\x71\x1f\0\
\xf1\x73\x1d\0\xf2\x74\x1c\0\xf3\x76\x1b\0\xf3\x78\x19\0\xf4\x79\x18\0\xf5\x7b\x17\0\xf5\x7d\x15\0\xf6\x7e\x14\0\xf6\x80\x13\0\xf7\x82\x12\0\xf7\x84\x10\0\
\xf8\x85\x0f\0\xf8\x87\x0e\0\xf8\x89\x0c\0\xf9\x8b\x0b\0\xf9\x8c\x0a\0\xf9\x8e\x09\0\xfa\x90\x08\0\xfa\x92\x07\0\xfa\x94\x07\0\xfb\x96\x06\0\xfb\x97\x06\0\
\xfb\x99\x06\0\xfb\x9b\x06\0\xfb\x9d\x07\0\xfc\x9f\x07\0\xfc\xa1\x08\0\xfc\xa3\x09\0\xfc\xa5\x0a\0\xfc\xa6\x0c\0\xfc\xa8\x0d\0\xfc\xaa\x0f\0\xfc\xac\x11\0\
\xfc\xae\x12\0\xfc\xb0\x14\0\xfc\xb2\x16\0\xfc\xb4\x18\0\xfb\xb6\x1a\0\xfb\xb8\x1d\0\xfb\xba\x1f\0\xfb\xbc\x21\0\xfb\xbe\x23\0\xfa\xc0\x26\0\xfa\xc2\x28\0\
\xfa\xc4\x2a\0\xfa\xc6\x2d\0\xf9\xc7\x2f\0\xf9\xc9\x32\0\xf9\xcb\x35\0\xf8\xcd\x37\0\xf8\xcf\x3a\0\xf7\xd1\x3d\0\xf7\xd3\x40\0\xf6\xd5\x43\0\xf6\xd7\x46\0\
\xf5\xd9\x49\0\xf5\xdb\x4c\0\xf4\xdd\x4f\0\xf4\xdf\x53\0\xf4\xe1\x56\0\xf3\xe3\x5a\0\xf3\xe5\x5d\0\xf2\xe6\x61\0\xf2\xe8\x65\0\xf2\xea\x69\0\xf1\xec\x6d\0\
\xf1\xed\x71\0\xf1\xef\x75\0\xf1\xf1\x79\0\xf2\xf2\x7d\0\xf2\xf4\x82\0\xf3\xf5\x86\0\xf3\xf6\x8a\0\xf4\xf8\x8e\0\xf5\xf9\x92\0\xf6\xfa\x96\0\xf8\xfb\x9a\0\
\xf9\xfc\x9d\0\xfa\xfd\xa1\0\xfc\xff\xa4\0'
SDL_PAL_INFERNO = (ctypes.c_uint8 * len(SDL_PAL_INFERNO_L))(*SDL_PAL_INFERNO_L)

# palette from https://github.com/groupgets/GetThermal/blob/master/src/dataformatter.cpp
SDL_PAL_IRONBLACK_L = b'\
\xff\xff\xff\0\xfd\xfd\xfd\0\xfb\xfb\xfb\0\xf9\xf9\xf9\0\xf7\xf7\xf7\0\xf5\xf5\xf5\0\xf3\xf3\xf3\0\xf1\xf1\xf1\0\xef\xef\xef\0\xed\xed\xed\0\xeb\xeb\xeb\0\
\xe9\xe9\xe9\0\xe7\xe7\xe7\0\xe5\xe5\xe5\0\xe3\xe3\xe3\0\xe1\xe1\xe1\0\xdf\xdf\xdf\0\xdd\xdd\xdd\0\xdb\xdb\xdb\0\xd9\xd9\xd9\0\xd7\xd7\xd7\0\xd5\xd5\xd5\0\
\xd3\xd3\xd3\0\xd1\xd1\xd1\0\xcf\xcf\xcf\0\xcd\xcd\xcd\0\xcb\xcb\xcb\0\xc9\xc9\xc9\0\xc7\xc7\xc7\0\xc5\xc5\xc5\0\xc3\xc3\xc3\0\xc1\xc1\xc1\0\xbf\xbf\xbf\0\
\xbd\xbd\xbd\0\xbb\xbb\xbb\0\xb9\xb9\xb9\0\xb7\xb7\xb7\0\xb5\xb5\xb5\0\xb3\xb3\xb3\0\xb1\xb1\xb1\0\xaf\xaf\xaf\0\xad\xad\xad\0\xab\xab\xab\0\xa9\xa9\xa9\0\
\xa7\xa7\xa7\0\xa5\xa5\xa5\0\xa3\xa3\xa3\0\xa1\xa1\xa1\0\x9f\x9f\x9f\0\x9d\x9d\x9d\0\x9b\x9b\x9b\0\x99\x99\x99\0\x97\x97\x97\0\x95\x95\x95\0\x93\x93\x93\0\
\x91\x91\x91\0\x8f\x8f\x8f\0\x8d\x8d\x8d\0\x8b\x8b\x8b\0\x89\x89\x89\0\x87\x87\x87\0\x85\x85\x85\0\x83\x83\x83\0\x81\x81\x81\0\x7e\x7e\x7e\0\x7c\x7c\x7c\0\
\x7a\x7a\x7a\0\x78\x78\x78\0\x76\x76\x76\0\x74\x74\x74\0\x72\x72\x72\0\x70\x70\x70\0\x6e\x6e\x6e\0\x6c\x6c\x6c\0\x6a\x6a\x6a\0\x68\x68\x68\0\x66\x66\x66\0\
\x64\x64\x64\0\x62\x62\x62\0\x60\x60\x60\0\x5e\x5e\x5e\0\x5c\x5c\x5c\0\x5a\x5a\x5a\0\x58\x58\x58\0\x56\x56\x56\0\x54\x54\x54\0\x52\x52\x52\0\x50\x50\x50\0\
\x4e\x4e\x4e\0\x4c\x4c\x4c\0\x4a\x4a\x4a\0\x48\x48\x48\0\x46\x46\x46\0\x44\x44\x44\0\x42\x42\x42\0\x40\x40\x40\0\x3e\x3e\x3e\0\x3c\x3c\x3c\0\x3a\x3a\x3a\0\
\x38\x38\x38\0\x36\x36\x36\0\x34\x34\x34\0\x32\x32\x32\0\x30\x30\x30\0\x2e\x2e\x2e\0\x2c\x2c\x2c\0\x2a\x2a\x2a\0\x28\x28\x28\0\x26\x26\x26\0\x24\x24\x24\0\
\x22\x22\x22\0\x20\x20\x20\0\x1e\x1e\x1e\0\x1c\x1c\x1c\0\x1a\x1a\x1a\0\x18\x18\x18\0\x16\x16\x16\0\x14\x14\x14\0\x12\x12\x12\0\x10\x10\x10\0\x0e\x0e\x0e\0\
\x0c\x0c\x0c\0\x0a\x0a\x0a\0\x08\x08\x08\0\x06\x06\x06\0\x04\x04\x04\0\x02\x02\x02\0\x00\x00\x00\0\x00\x00\x09\0\x02\x00\x10\0\x04\x00\x18\0\x06\x00\x1f\0\
\x08\x00\x26\0\x0a\x00\x2d\0\x0c\x00\x35\0\x0e\x00\x3c\0\x11\x00\x43\0\x13\x00\x4a\0\x15\x00\x52\0\x17\x00\x59\0\x19\x00\x60\0\x1b\x00\x67\0\x1d\x00\x6f\0\
\x1f\x00\x76\0\x24\x00\x78\0\x29\x00\x79\0\x2e\x00\x7a\0\x33\x00\x7b\0\x38\x00\x7c\0\x3d\x00\x7d\0\x42\x00\x7e\0\x47\x00\x7f\0\x4c\x01\x80\0\x51\x01\x81\0\
\x56\x01\x82\0\x5b\x01\x83\0\x60\x01\x84\0\x65\x01\x85\0\x6a\x01\x86\0\x6f\x01\x87\0\x74\x01\x88\0\x79\x01\x88\0\x7d\x02\x89\0\x82\x02\x89\0\x87\x03\x89\0\
\x8b\x03\x8a\0\x90\x03\x8a\0\x95\x04\x8a\0\x99\x04\x8b\0\x9e\x05\x8b\0\xa3\x05\x8b\0\xa7\x05\x8c\0\xac\x06\x8c\0\xb1\x06\x8c\0\xb5\x07\x8d\0\xba\x07\x8d\0\
\xbd\x0a\x89\0\xbf\x0d\x84\0\xc2\x10\x7f\0\xc4\x13\x79\0\xc6\x16\x74\0\xc8\x19\x6f\0\xcb\x1c\x6a\0\xcd\x1f\x65\0\xcf\x22\x5f\0\xd1\x25\x5a\0\xd4\x28\x55\0\
\xd6\x2b\x50\0\xd8\x2e\x4b\0\xda\x31\x45\0\xdd\x34\x40\0\xdf\x37\x3b\0\xe0\x39\x31\0\xe1\x3c\x2f\0\xe2\x40\x2c\0\xe3\x43\x2a\0\xe4\x47\x27\0\xe5\x4a\x25\0\
\xe6\x4e\x22\0\xe7\x51\x20\0\xe7\x55\x1d\0\xe8\x58\x1b\0\xe9\x5c\x18\0\xea\x5f\x16\0\xeb\x63\x13\0\xec\x66\x11\0\xed\x6a\x0e\0\xee\x6d\x0c\0\xef\x70\x0c\0\
\xf0\x74\x0c\0\xf0\x77\x0c\0\xf1\x7b\x0c\0\xf1\x7f\x0c\0\xf2\x82\x0c\0\xf2\x86\x0c\0\xf3\x8a\x0c\0\xf3\x8d\x0d\0\xf4\x91\x0d\0\xf4\x95\x0d\0\xf5\x98\x0d\0\
\xf5\x9c\x0d\0\xf6\xa0\x0d\0\xf6\xa3\x0d\0\xf7\xa7\x0d\0\xf7\xab\x0d\0\xf8\xaf\x0e\0\xf8\xb2\x0f\0\xf9\xb6\x10\0\xf9\xb9\x12\0\xfa\xbd\x13\0\xfa\xc0\x14\0\
\xfb\xc4\x15\0\xfb\xc7\x16\0\xfc\xcb\x17\0\xfc\xce\x18\0\xfd\xd2\x19\0\xfd\xd5\x1b\0\xfe\xd9\x1c\0\xfe\xdc\x1d\0\xff\xe0\x1e\0\xff\xe3\x27\0\xff\xe5\x35\0\
\xff\xe7\x43\0\xff\xe9\x51\0\xff\xea\x5f\0\xff\xec\x6d\0\xff\xee\x7b\0\xff\xf0\x89\0\xff\xf2\x97\0\xff\xf4\xa5\0\xff\xf6\xb3\0\xff\xf8\xc1\0\xff\xf9\xcf\0\
\xff\xfb\xdd\0\xff\xfd\xeb\0\xff\xff\x18\0'
SDL_PAL_IRONBLACK = (ctypes.c_uint8 * len(SDL_PAL_IRONBLACK_L))(*SDL_PAL_IRONBLACK_L)

SDL_PALS = {
    'grayscale': SDL_PAL_GRAYSCALE,
    'inferno': SDL_PAL_INFERNO,
    'ironblack': SDL_PAL_IRONBLACK,
}

SDL_WINDOW_FULLSCREEN = 0x00000001
SDL_WINDOW_RESIZABLE = 0x00000020
SDL_WINDOW_FULLSCREEN_DESKTOP = (SDL_WINDOW_FULLSCREEN | 0x00001000)
SDL_WINDOWPOS_UNDEFINED = 0x1FFF0000

SDL_MESSAGEBOX_ERROR = 0x00000010

def SDL_FOURCC(a, b, c, d):
    return (ord(a) << 0) | (ord(b) << 8) | (ord(c) << 16) | (ord(d) << 24)
SDL_PIXELFORMAT_YUY2 = SDL_FOURCC('Y', 'U', 'Y', '2')
SDL_PIXELFORMAT_YV12 = SDL_FOURCC('Y', 'V', '1', '2')
SDL_PIXELFORMAT_YVYU = SDL_FOURCC('Y', 'V', 'Y', 'U')
SDL_PIXELFORMAT_UYVY = SDL_FOURCC('U', 'Y', 'V', 'Y')
SDL_PIXELFORMAT_VYUY = SDL_FOURCC('V', 'Y', 'U', 'Y')
SDL_PIXELFORMAT_NV12 = SDL_FOURCC('N', 'V', '1', '2')
SDL_PIXELFORMAT_NV21 = SDL_FOURCC('N', 'V', '2', '1')
SDL_PIXELFORMAT_IYUV = SDL_FOURCC('I', 'Y', 'U', 'V')
SDL_PIXELFORMAT_RGB24 = 386930691
SDL_PIXELFORMAT_BGR24 = 390076419
SDL_PIXELFORMAT_BGR888 = 374740996 #XBGR8888
SDL_PIXELFORMAT_RGB565 = 353701890
SDL_TEXTUREACCESS_STREAMING = 1

SDL_Keycode = ctypes.c_int32
SDL_Scancode = ctypes.c_int
_event_pad_size = 56 if ctypes.sizeof(ctypes.c_void_p) <= 8 else 64

class SDL_Keysym(ctypes.Structure):
    _fields_ = [
        ('scancode', SDL_Scancode),
        ('sym', SDL_Keycode),
        ('mod', ctypes.c_uint16),
        ('unused', ctypes.c_uint32),
    ]

class SDL_KeyboardEvent(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('timestamp', ctypes.c_uint32),
        ('windowID', ctypes.c_uint32),
        ('state', ctypes.c_uint8),
        ('repeat', ctypes.c_uint8),
        ('padding2', ctypes.c_uint8),
        ('padding3', ctypes.c_uint8),
        ('keysym', SDL_Keysym),
    ]

class SDL_MouseButtonEvent(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('timestamp', ctypes.c_uint32),
        ('windowID', ctypes.c_uint32),
        ('which', ctypes.c_uint32),
        ('button', ctypes.c_uint8),
        ('state', ctypes.c_uint8),
        ('clicks', ctypes.c_uint8),
        ('padding1', ctypes.c_uint8),
        ('x', ctypes.c_int32),
        ('y', ctypes.c_int32),
    ]

class SDL_UserEvent(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('timestamp', ctypes.c_uint32),
        ('windowID', ctypes.c_uint32),
        ('code', ctypes.c_int32),
        ('data1', ctypes.c_void_p),
        ('data2', ctypes.c_void_p),
    ]


class SDL_Event(ctypes.Union):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('key', SDL_KeyboardEvent),
        ('button', SDL_MouseButtonEvent),
        ('user', SDL_UserEvent),
        ('padding', (ctypes.c_uint8 * _event_pad_size)),
    ]

tj_init_decompress = turbojpeg.tjInitDecompress
tj_init_decompress.restype = ctypes.c_void_p
#tjhandle tjInitDecompress()

tj_decompress = turbojpeg.tjDecompress2
tj_decompress.argtypes = [ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_ubyte), ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.c_int]
tj_decompress.restype = ctypes.c_int
#int tjDecompress2(tjhandle handle,
#                  const unsigned char *jpegBuf, unsigned long jpegSize,
#                  unsigned char *dstBuf,
#                  int width, int pitch, int height, int pixelFormat,
#                  int flags);

tj_get_error_str = turbojpeg.tjGetErrorStr
tj_get_error_str.restype = ctypes.c_char_p
#char* tjGetErrorStr()

tj_destroy = turbojpeg.tjDestroy
tj_destroy.argtypes = [ctypes.c_void_p]
tj_destroy.restype = ctypes.c_int
# int tjDestroy(tjhandle handle);

TJPF_RGB = 0

class V4L2Camera(Thread):
    def __init__(self, device):
        super().__init__()
        self.device = device
        self.width = 0
        self.height = 0
        self.pixelformat = 0
        self.bytesperline = 0
        self.stopped = False
        self.pipe = None
        self.num_cap_bufs = 6
        self.cap_bufs = []

        self.fd = os.open(self.device, os.O_RDWR, 0)

        self.init_device()
        self.init_buffers()


    def init_device(self):
        cap = v4l2_capability()
        fmt = v4l2_format()
        fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE

        ioctl(self.fd, VIDIOC_QUERYCAP, cap)
        ioctl(self.fd, VIDIOC_G_FMT, fmt)

        # some camera need an S_FMT to work
        try:
            ioctl(self.fd, VIDIOC_S_FMT, fmt)
        except Exception as e:
            logging.warning(f'V4L2FmtCtrls: Can\'t set fmt {e}')

        if not (cap.capabilities & V4L2_CAP_VIDEO_CAPTURE):
            logging.error(f'{self.device} is not a video capture device')
            sys.exit(3)

        if not (cap.capabilities & V4L2_CAP_STREAMING):
            logging.error(f'{self.device} does not support streaming i/o')
            sys.exit(3)

        self.width = fmt.fmt.pix.width
        self.height = fmt.fmt.pix.height
        self.pixelformat = fmt.fmt.pix.pixelformat
        self.bytesperline = fmt.fmt.pix.bytesperline


    def init_buffers(self):
        req = v4l2_requestbuffers()

        req.count = self.num_cap_bufs
        req.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        req.memory = V4L2_MEMORY_MMAP


        try:
            ioctl(self.fd, VIDIOC_REQBUFS, req)
        except Exception as e:
            logging.error(f'Video buffer request failed on {self.device} ({e})')
            sys.exit(3)

        if req.count != self.num_cap_bufs:
            logging.error(f'Insufficient buffer memory on {self.device}')
            sys.exit(3)

        for i in range(req.count):
            buf = v4l2_buffer()
            buf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
            buf.memory = req.memory
            buf.index = i

            ioctl(self.fd, VIDIOC_QUERYBUF, buf)

            if req.memory == V4L2_MEMORY_MMAP:
                buf.buffer = mmap.mmap(self.fd, buf.length,
                    flags=mmap.MAP_SHARED | 0x08000, #MAP_POPULATE
                    prot=mmap.PROT_READ | mmap.PROT_WRITE,
                    offset=buf.m.offset)

            self.cap_bufs.append(buf)

    def capture_loop(self):
        for buf in self.cap_bufs:
            ioctl(self.fd, VIDIOC_QBUF, buf)

        qbuf = v4l2_buffer()
        qbuf.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
        qbuf.memory = self.cap_bufs[0].memory

        poll = select.poll()
        poll.register(self.fd, select.POLLIN)

        while not self.stopped:
            # DQBUF can block forever, so poll with 1000 ms timeout before
            if len(poll.poll(1000)) == 0:
                logging.warning(f'{self.device}: timeout occured')
                continue
            
            ioctl(self.fd, VIDIOC_DQBUF, qbuf)

            buf = self.cap_bufs[qbuf.index]
            buf.bytesused = qbuf.bytesused
            buf.timestamp = qbuf.timestamp

            self.pipe.write_buf(buf)

            ioctl(self.fd, VIDIOC_QBUF, buf)


    def start_capturing(self):
        ioctl(self.fd, VIDIOC_STREAMON, struct.pack('I', V4L2_BUF_TYPE_VIDEO_CAPTURE))
        self.capture_loop()
        ioctl(self.fd, VIDIOC_STREAMOFF, struct.pack('I', V4L2_BUF_TYPE_VIDEO_CAPTURE))

    def stop_capturing(self):
        self.stopped = True

    # thread start
    def run(self):
        self.start_capturing()
    
    # thread stop
    def stop(self):
        self.stop_capturing()
        self.join()


def V4L2Format2SDL(format):
    if format == V4L2_PIX_FMT_YUYV:
        return SDL_PIXELFORMAT_YUY2
    elif format == V4L2_PIX_FMT_YVYU:
        return SDL_PIXELFORMAT_YVYU
    elif format == V4L2_PIX_FMT_UYVY:
        return SDL_PIXELFORMAT_UYVY
    elif format == V4L2_PIX_FMT_NV12:
        return SDL_PIXELFORMAT_NV12
    elif format == V4L2_PIX_FMT_NV21:
        return SDL_PIXELFORMAT_NV21
    elif format == V4L2_PIX_FMT_YU12:
        return SDL_PIXELFORMAT_IYUV
    elif format == V4L2_PIX_FMT_YV12:
        return SDL_PIXELFORMAT_YV12
    elif format == V4L2_PIX_FMT_RGB565:
        return SDL_PIXELFORMAT_RGB565
    elif format == V4L2_PIX_FMT_RGB24:
        return SDL_PIXELFORMAT_RGB24
    elif format == V4L2_PIX_FMT_BGR24:
        return SDL_PIXELFORMAT_BGR24
    elif format == V4L2_PIX_FMT_RX24:
        return SDL_PIXELFORMAT_BGR888
    elif format in [V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG]:
        return SDL_PIXELFORMAT_RGB24
    # handling with surface+palette+texture, not here
    #elif format == V4L2_PIX_FMT_GREY:
    #    return SDL_PIXELFORMAT_INDEX8

    formats = 'Sorry, only YUYV, YVYU, UYVY, NV12, NV21, YU12, RGBP, RGB3, BGR3, RX24, MJPG, JPEG, GREY are supported yet.'
    logging.error(f'Invalid pixel format: {formats}')
    SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, b'Invalid pixel format', bytes(formats, 'utf-8'), None)
    sys.exit(3)

class SDLCameraWindow():
    def __init__(self, device, angle, flip, colormap):
        self.cam = V4L2Camera(device)
        self.cam.pipe = self
        width = self.cam.width
        height = self.cam.height

        self.fullscreen = False
        self.tj = None
        self.outbuffer = None
        self.bytesperline = self.cam.bytesperline
        self.surface = None

        self.angle = angle
        self.flip = flip
        self.colormap = colormap

        if self.cam.pixelformat in [V4L2_PIX_FMT_MJPEG, V4L2_PIX_FMT_JPEG]:
            self.tj = tj_init_decompress()
            # create rgb buffer
            buf_size = width * height * 3
            buf = ctypes.create_string_buffer(b"", buf_size)
            self.outbuffer = (ctypes.c_uint8 * buf_size).from_buffer(buf)
            self.bytesperline = width * 3

        if SDL_Init(SDL_INIT_VIDEO) != 0:
            logging.error(f'SDL_Init failed: {SDL_GetError()}')
            sys.exit(1)

        # create a new sdl user event type for new image events
        self.sdl_new_image_event = SDL_RegisterEvents(1)
        self.sdl_new_grey_image_event = SDL_RegisterEvents(1)

        self.new_image_event = SDL_Event()
        self.new_image_event.type = self.sdl_new_image_event

        self.new_grey_image_event = SDL_Event()
        self.new_grey_image_event.type = self.sdl_new_grey_image_event

        self.window = SDL_CreateWindow(bytes(device, 'utf-8'), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, width, height, SDL_WINDOW_RESIZABLE)
        if self.window == None:
            logging.error(f'SDL_CreateWindow failed: {SDL_GetError()}')
            sys.exit(1)
        self.renderer = SDL_CreateRenderer(self.window, -1, 0)
        if self.renderer == None:
            logging.error(f'SDL_CreateRenderer failed: {SDL_GetError()}')
            sys.exit(1)
        if SDL_RenderSetLogicalSize(self.renderer, width, height) != 0:
            logging.warning(f'SDL_RenderSetlogicalSize failed: {SDL_GetError()}')

        if self.cam.pixelformat != V4L2_PIX_FMT_GREY:
            self.texture = SDL_CreateTexture(self.renderer, V4L2Format2SDL(self.cam.pixelformat), SDL_TEXTUREACCESS_STREAMING, width, height)
            if self.texture == None:
                logging.error(f'SDL_CreateTexture failed: {SDL_GetError()}')
                sys.exit(1)
        else:
            self.surface = SDL_CreateRGBSurfaceFrom(self.outbuffer, self.cam.width, self.cam.height, 8, self.bytesperline, 0, 0, 0, 0)
            if self.surface == None:
                logging.error(f'SDL_CreateRGBSurfaceFrom failed: {SDL_GetError()}')
                sys.exit(1)
            self.set_colormap(self.colormap)

    def write_buf(self, buf):
        ptr = (ctypes.c_uint8 * buf.bytesused).from_buffer(buf.buffer)
        event = self.new_image_event if self.cam.pixelformat != V4L2_PIX_FMT_GREY else self.new_grey_image_event

        if self.cam.pixelformat == V4L2_PIX_FMT_MJPEG or self.cam.pixelformat == V4L2_PIX_FMT_JPEG:
            if tj_decompress(self.tj, ptr, buf.bytesused, self.outbuffer, self.cam.width, self.bytesperline, self.cam.height, TJPF_RGB, 0) != 0:
                logging.warning(f'tj_decompress failed: {tj_get_error_str()}')
                return
            ptr = self.outbuffer

        event.user.data1 = ctypes.cast(ptr, ctypes.c_void_p)
        if SDL_PushEvent(ctypes.byref(event)) < 0:
            logging.warning(f'SDL_PushEvent failed: {SDL_GetError()}')

    def event_loop(self):
        event = SDL_Event()
        while SDL_WaitEvent(ctypes.byref(event)) != 0:
            if event.type == SDL_QUIT:
                self.stop_capturing()
                break
            elif event.type == SDL_KEYDOWN and event.key.repeat == 0:
                if event.key.keysym.sym == SDLK_q or event.key.keysym.sym == SDLK_ESCAPE:
                    self.stop_capturing()
                    break
                if event.key.keysym.sym == SDLK_f:
                    self.toggle_fullscreen()
                elif event.key.keysym.sym == SDLK_r and event.key.keysym.mod == KMOD_NONE:
                    self.rotate(90)
                elif event.key.keysym.sym == SDLK_r and event.key.keysym.mod | KMOD_SHIFT:
                    self.rotate(-90)
                elif event.key.keysym.sym == SDLK_m and event.key.keysym.mod == KMOD_NONE:
                    self.mirror(1)
                elif event.key.keysym.sym == SDLK_m and event.key.keysym.mod | KMOD_SHIFT:
                    self.mirror(-1)
                elif event.key.keysym.sym == SDLK_c and event.key.keysym.mod == KMOD_NONE:
                    self.step_colormap(1)
                elif event.key.keysym.sym == SDLK_c and event.key.keysym.mod | KMOD_SHIFT:
                    self.step_colormap(-1)
            elif event.type == SDL_MOUSEBUTTONUP and \
                event.button.button == SDL_BUTTON_LEFT and \
                event.button.clicks == 2:
                    self.toggle_fullscreen()
            elif event.type == self.sdl_new_image_event:
                if SDL_UpdateTexture(self.texture, None, event.user.data1, self.bytesperline) != 0:
                    logging.warning(f'SDL_UpdateTexture failed: {SDL_GetError()}')
                if SDL_RenderClear(self.renderer) != 0:
                    logging.warning(f'SDL_RenderClear failed: {SDL_GetError()}')
                if SDL_RenderCopyEx(self.renderer, self.texture, None, None, self.angle, None, self.flip) != 0:
                    logging.warning(f'SDL_RenderCopy failed: {SDL_GetError()}')
                SDL_RenderPresent(self.renderer)
            elif event.type == self.sdl_new_grey_image_event:
                self.surface[0].pixels = event.user.data1
                texture = SDL_CreateTextureFromSurface(self.renderer, self.surface)
                if texture == None:
                    logging.warning(f'SDL_CreateTextureFromSurface failed: {SDL_GetError()}')
                    return
                if SDL_RenderClear(self.renderer) != 0:
                    logging.warning(f'SDL_RenderClear failed: {SDL_GetError()}')
                if SDL_RenderCopyEx(self.renderer, texture, None, None, self.angle, None, self.flip) != 0:
                    logging.warning(f'SDL_RenderCopy failed: {SDL_GetError()}')
                SDL_RenderPresent(self.renderer)
                SDL_DestroyTexture(texture)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        SDL_SetWindowFullscreen(self.window, SDL_WINDOW_FULLSCREEN_DESKTOP if self.fullscreen else 0)

    def rotate(self, angle):
        self.angle += angle
        self.angle %= 360

    def mirror(self, flip):
        self.flip += flip
        self.flip %= 4

    def set_colormap(self, colormap):
        if colormap not in SDL_PALS:
            logging.warning(f'set_colormap: invalid colormap name ({colormap}) not in {list(SDL_PALS.keys())} using grayscale')
            colormap = 'grayscale'

        pal = SDL_PALS.get(colormap)    

        self.colormap = colormap

        if self.surface == None:
            logging.warning(f'set_colormap: only for GREY streams')
            return
        SDL_SetPaletteColors(self.surface[0].format[0].palette, pal, 0, 256)

    def step_colormap(self, step):
        cms = list(SDL_PALS.keys())
        step = (cms.index(self.colormap) + step) % len(cms)
        self.set_colormap(cms[step])

    def start_capturing(self):
        self.cam.start()
        self.event_loop()

    def stop_capturing(self):
        self.cam.stop()

    def close(self):
        tj_destroy(self.tj)
        SDL_DestroyWindow(self.window)
        SDL_Quit()


def usage():
    print(f'usage: {sys.argv[0]} [--help] [-d DEVICE] [-r ANGLE] [-m FLIP] [-c COLORMAP]\n')
    print(f'optional arguments:')
    print(f'  -h, --help         show this help message and exit')
    print(f'  -d DEVICE          use DEVICE, default /dev/video0')
    print(f'  -r ANGLE           rotate the image by ANGLE, default 0')
    print(f'  -m FLIP            mirror the image by FLIP, default no, (no, h, v, hv)')
    print(f'  -c COLORMAP        set colormap for GREY streams, default grayscale')
    print(f'                                      (grayscale, inferno, ironblack)')
    print()
    print(f'example:')
    print(f'  {sys.argv[0]} -d /dev/video2')
    print()
    print(f'shortcuts:')
    print(f'  f: toggle fullscreen')
    print(f'  r: ANGLE +90 (shift+r -90)')
    print(f'  m: FLIP next (shift+m prev)')
    print(f'  c: COLORMAP next (shift+c prev)')


def main():
    try:
        arguments, values = getopt.getopt(sys.argv[1:], 'hd:r:m:c:', ['help'])
    except getopt.error as err:
        print(err)
        usage()
        sys.exit(2)

    device = '/dev/video0'
    angle = 0
    flip = 0
    colormap = 'grayscale'

    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif current_argument == '-d':
            device = current_value
        elif current_argument == '-r':
            angle = int(current_value)
        elif current_argument == '-m':
            if current_value == 'no':
                flip = 0
            elif current_value == 'h':
                flip = 1
            elif current_value == 'v':
                flip = 2
            elif current_value == 'hv':
                flip = 3
            else:
                print(f'invalid FLIP value: {current_value}')
                usage()
                sys.exit(1)
        elif current_argument == '-c':
            colormap = current_value


    os.environ['SDL_VIDEO_X11_WMCLASS'] = 'hu.irl.cameractrls'

    win = SDLCameraWindow(device, angle, flip, colormap)
    win.start_capturing()
    win.close()


if __name__ == '__main__':
    main()
