#!/usr/bin/env python3

from code.config import getConfig, writeConfig
from code.auth import Auth
from code.excluded import read_excluded, remove_excluded
from code.submissions import get_submissions, filter_submissions
from code.filesys import delete_stale_images
from code.download import download_image

import praw
from unidecode import unidecode
import requests
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import os
import re
from time import strftime,sleep
import io
import sys
import pickle
import calendar
import time
import logging

dataFile_ = ".reddit_image_data"


logging.basicConfig()
log = logging.getLogger('reddit_image_download')


def main(authfile):

    log.info("reddit_image_download.py")

    cp = getConfig(log=log)
    log.setLevel(getattr(logging, cp['logging']['level'].upper()))
    log.info("log level set to %s", cp['logging']['level'])
    writeConfig(cp, log=log)

    auth = Auth()
    auth.readFromFile(authfile)
    r = auth.login()
    log.info("connected to reddit")

    imagePath = os.path.expanduser(cp['paths']['images'])
    log.debug("using image path %s", imagePath)
    if not os.path.exists(imagePath):
        os.makedirs(imagePath)
        log.info("created path %s", imagePath)
    os.chdir(imagePath)
    log.info("changed to directory %s", imagePath)

    download_bytes = 0
    to_download = []
    filenames_to_download = set()

    fileLimit=cp.getint('limits', 'posts')
    submissions = get_submissions(r, fileLimit, cp)
    
    for s in filter_submissions(submissions, cp, log):
        username = "[deleted]" if s.author is None else s.author.name
        to_download.append({'url': s.url, 'title': s.title, 'user': username, 'created': s.created, 'subreddit': s.subreddit.display_name, 'id': s.id})
        filenames_to_download.add(s.id)
    log.info("%d items in download list", len(to_download))

    keepfiles = delete_stale_images(filenames_to_download, dataFile_, log)
    
    # remove excluded URLs
    excluded = read_excluded(dataFile_, log=log)
    remove_excluded(to_download, excluded, log)
    
    count = 0
    downloaded = 0
    downlaod_bytes = 0
    max_download = cp.getint('limits', 'images')
    log.info("downloading images")
    for data in to_download:
        if count >= max_download:
            log.info("reached %d images", count)
            break
        
        if any([True for f in keepfiles if f.startswith(data['id'])]):
            log.debug("already have %s", data['id'])
            # already got this file!
            count += 1
            continue

        responses = download_image(data, log)
        if not responses:
            continue
        download_bytes += sum(len(x.content) for x in responses)
        response = responses[-1]

        # edit data
        try:
            bio = io.BytesIO(response.content)
            filename = editImage(bio, data, cp)
            count += 1
            downloaded += 1
            log.debug("wrote %s (%d)", filename, count)
        except Exception as e:
            log.exception("error: %s, url=%s", e, s.url)
            excluded.add(data['id'])
            bio.close()

    
    log.info("%d files total", kept + downloaded)
    log.info("downloaded %d bytes total", download_bytes)
    with open(dataFile, "wb") as f:
        pickle.dump(excluded, f)
    log.info("%d files on exluded list", len(excluded))
    
    

def editImage(bio, data, cp):
    log.info("editing %s", data['id'])
    im = Image.open(bio).convert('RGBA')
    
    # resize image
    w,h = im.size
    h_scale = cp.getfloat('processing', 'height') / h
    w_scale = cp.getfloat('processing', 'width') / w
    scale = min(w_scale, h_scale)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    new_size = (new_w, new_h)
    if scale <= 0.2:
        im = im.resize(new_size, Image.ANTIALIAS)
    else:
        im = im.resize(new_size, Image.BICUBIC)
    overlay = Image.new('RGBA', im.size, (255,255,255,0))
    
        
    # add text
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.truetype(cp['title-font']['name'], cp.getint('title-font', 'size'))
    timestamp_font = ImageFont.truetype(cp['timestamp-font']['name'], cp.getint('timestamp-font', 'size'))
    
    txt = data['title']
    txt_before = txt   
 
    # do a little string replacement
    txt = re.sub(r'[\[(]\s*[0-9,]+\s*[xX\u00D7]\s*[0-9,]+\s*[\])]', '', txt, flags=re.UNICODE)
    txt = re.sub(r'[\[(][oO][cCsS][\])]', '', txt)
    txt = re.sub(r' +', ' ', txt)

    timestamp = time.strftime("%m-%d   %H:%M")
    timestamp_w, timestamp_h = draw.textsize(timestamp, timestamp_font)

    if txt != txt_before:
        log.info("modified text: %s -> %s", txt_before, txt)
    
    words = txt.split()
    subreddit = data['subreddit']
    # remove "porn" from the name
    if subreddit.lower().endswith('porn'):
        subreddit = subreddit[0:-4]
    words.append("(/u/{} - {})".format(data['user'], subreddit))
    text = ""
    vert_buffer_top = 5
    vert_buffer_bottom = 10
    horiz_buffer = 10
    max_w = new_w - 2 * horiz_buffer
    for word in words:
        if len(text) == 0:
            text = word
            continue
        proposed_size = draw.multiline_textsize(text + " " + word, font)
        if proposed_size[0] > max_w:
            text = text + "\n" + word
        else:
            text = text + " " + word
        
    text_size = draw.multiline_textsize(text + " " + word, font)
    text_xpos = horiz_buffer
    text_ypos = new_h - vert_buffer_bottom - text_size[1]

    # go a few pixels up if at the bottom of the TV
    draw.rectangle(im.size + (0, text_ypos-vert_buffer_top), (0,0,0,128))
    draw.text((2, im.size[1]-timestamp_h-2),
              timestamp, fill=(255,255,255,128), font=timestamp_font)
    draw.multiline_text((text_xpos, text_ypos),text,fill=(255,255,255),font=font)
    #draw.text((0,50), text, font=font)
    result = Image.alpha_composite(im, overlay)
    rgb_result = result.convert('RGB')
    del draw
    filename = data['id'] + '.jpg'
    rgb_result.save(filename, quality=100)
    bio.close()
    return filename
    
    
if __name__ == "__main__":
    argv = sys.argv
    if len(argv) < 2:
        argv.append('auth.txt')
    elif len(argv) > 2:
        raise RuntimeError('too many arguments')
    main(argv[1])
    
