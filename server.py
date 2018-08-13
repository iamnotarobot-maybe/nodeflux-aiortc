import argparse
import asyncio
import json
import logging
import os
import wave

import cv2
from aiohttp import web

from aiortc import (RTCPeerConnection, RTCSessionDescription)

ROOT = os.path.dirname(__file__)

vcap = cv2.VideoCapture("rtsp://184.72.239.149/vod/mp4:BigBuckBunny_175k.mov")


class VideoTransformTrack():
    def __init__(self):
        self.received = asyncio.Queue(maxsize=1)

    async def recv(self):
        frame = await self.received.get()

        return frame


async def consume_video(local_video):
    """
    Drain incoming video, and echo it back.
    """
    while True:
        ret, frame = vcap.read()

        # we are only interested in the latest frame
        if local_video.received.full():
            await local_video.received.get()

        await local_video.received.put(frame)


async def index(request):
    content = open(os.path.join(ROOT, 'index.html'), 'r').read()
    return web.Response(content_type='text/html', text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, 'client.js'), 'r').read()
    return web.Response(content_type='application/javascript', text=content)


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params['sdp'], type=params['type'])

    local_video = VideoTransformTrack()

    pc = RTCPeerConnection()
    pc._consumers = []
    pcs.append(pc)

    @pc.on('datachannel')
    def on_datachannel(channel):
        @channel.on('message')
        def on_message(message):
            channel.send('pong')

    pc.addTrack(local_video)
    pc._consumers.append(asyncio.ensure_future(consume_video(local_video)))

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type='application/json',
        text=json.dumps({
            'sdp': pc.localDescription.sdp,
            'type': pc.localDescription.type
        }))


pcs = []


async def on_shutdown(app):
    # stop audio / video consumers
    for pc in pcs:
        for c in pc._consumers:
            c.cancel()

    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='WebRTC audio / video / data-channels demo')
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port for HTTP server (default: 8080)')
    parser.add_argument('--verbose', '-v', action='count')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get('/', index)
    app.router.add_get('/client.js', javascript)
    app.router.add_post('/offer', offer)
    web.run_app(app, port=args.port, host='127.0.0.1')
