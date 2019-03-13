#!/usr/bin/env python3

from code.config import getConfig, writeConfig
from code.auth import Auth
from code.excluded import read_excluded
from code.submissions import get_submissions, filter_submissions

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

    excluded_ids = read_excluded(dataFile_, log=log)

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

    log.info("examining existing files")
    contents = os.listdir('.')
    keepfiles = set()
    for filename in sorted(contents):
        deleteFile = True
        if os.path.isdir(filename):
            continue
        if filename == dataFile_:
            continue
        for fname in [f for f in filenames_to_download if filename.startswith(f + '.')]:
            log.debug("file %s already downloaded", fname)
            keepfiles.add(filename)
            deleteFile = False
            break
        if deleteFile:
            log.info("deleting %s", filename)
            os.remove(filename)
    
    kept = len(keepfiles)
    log.info("keeping %d files", kept)
    
    # remove excluded URLs
    for entry in [entry for entry in to_download if entry['id'] in excluded_ids]:
        log.info("excluded id %s", entry['id'])
    to_download = [entry for entry in to_download if entry['id'] not in excluded_ids]
    old_excluded = len(excluded_ids)
    excluded = set([entry for entry in excluded_ids if entry in filenames])
    if len(excluded_ids) < old_excluded:
        log.info("removed %d entries from excluded list", old_excluded - len(excluded))
    
    count = 0
    downloaded = 0
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

        url = data['url']
       
        # get stupid flickr source if this is a base page
        mode = ''
        unique_id = ''
        old_url = url
        if re.search('[./]flickr.com', url):
            log.debug("found flickr base page, transforming url")
            flickr_filename = url.split('/')[-1]
            if '.' not in flickr_filename:
                m = re.search(r'^.*flickr.com/photos/([^/]+)/([^/]+)', url)
                if m and m.group(2) not in ['sets', 'items']:
                    mode = 'flickr'
                    unique_id = m.group(2)
                    url = m.group(0) + '/sizes/k'
                    log.debug("new url %s", url)
       
        response = requests.get(url)
        download_bytes += len(response.content)
        
        # get stupid imgur source if this is a base page
        if re.search('imgur\.com', url):
            log.debug("found imgur base page, finding source file")
            imgur_filename = url.split('/')[-1]
            if '.' not in imgur_filename:
                #print response.content
                # we need to get the actual imgur source file
                m = re.search(r'(//i\.imgur\.com/{}\.[^"]+)"'.format(imgur_filename), response.content.decode('utf-8'))
                if m:
                    log.debug("encountered imgur redirect: %s -> %s}", url, m.group(1))
                    response = requests.get("https:{}".format(m.group(1)))
                    download_bytes += len(response.content)
                else:
                    m = re.search(r'(//i\.imgur\.com/[a-zA-Z0-9]{2,}\.[^"]+)"', response.content.decode('utf-8'))
                    if m:
                        log.debug("trying album redirect: %s -> %s", url, m.group(1))
                        response = requests.get("https:{}".format(m.group(1)))
                        download_bytes += len(response.content)
                    else:
                        log.info("could not get imgur redirect for %s (%s)", url, data['title'])
        if mode == 'flickr':
            m = re.search(r'//[^"]+' + unique_id + r'[^"]+_d\.[^"]+', response.content.decode('utf-8'))
            if m:
                log.debug("trying flickr redirect: %s -> %s", old_url, m.group(0))
                response = requests.get("https:{}".format(m.group(0)))
                download_bytes += len(response.content)
            else:
                log.info("could not get flickr redirect for %s (%s)", url, data['title'])


        log.info("downloaded %s (%s - %s) (%d bytes)", url, data['subreddit'], data['title'], len(response.content))
        sleep(2)

        # edit data
        try:
            bio = io.BytesIO(response.content)
            filename = editImage(bio, data, cp)
            count += 1
            downloaded += 1
            log.debug("wrote %s (%d)", filename, count)
        except Exception as e:
            log.exception("error: %s, url=%s", e, url)
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
    
