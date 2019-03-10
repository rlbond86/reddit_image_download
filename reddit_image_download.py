#!/usr/bin/env python3


import praw
import os
import re
from unidecode import unidecode
import requests
from time import strftime,sleep
import io
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import sys
import pickle
import calendar
import time


imageFolder = "~/reddit_images"
dataFile_ = "~/.reddit_image_data"
fontSize = 28
numDownload = 120
numRead = 250

def main(authfile):
    
    with open(authfile, 'r') as f:
        lines = f.readlines()
        cid = lines[0].strip()
        csec = lines[1].strip()

    print("")
    print("Reddit sfw_porn fetch, {}".format(strftime("%Y-%m-%d %H:%M:%S")))

    dataFile = os.path.expanduser(dataFile_)
    excluded = set()
    try:
        with open(dataFile, 'rb') as f:
            excluded = pickle.load(f)
            print("- Loaded {} excluded files".format(len(excluded)))
    except:
        print("- Could not load excluded files list")

    fileLimit=numRead
    download_bytes = 0
    d = os.path.expanduser(imageFolder)
    if not os.path.exists(d):
        os.makedirs(d)
    os.chdir(d)
     
    to_download = []
    filenames = set()

    r = praw.Reddit(client_id=cid, client_secret=csec, user_agent="/u/rlbond86 image download script")
    sfwp_mreddit = r.multireddit('rlbond86', 'sfwp_network')
    submissions = sfwp_mreddit.hot(limit=fileLimit)
    
    for s in submissions:
        if s.over_18:
            continue
        if s.selftext_html is not None:
            continue
        if re.search(r'reddit.com/r', s.url):
            continue
        if s.url.endswith('/'):
            continue
        if s.url.endswith('.gif') or s.url.endswith('.gifv'):
            continue
        if calendar.timegm(time.gmtime()) - s.created_utc > 7*24*60*60:
            # over a week old
            continue
            
        url = s.url
        if url == '':
            continue
            
        to_download.append({'url': url, 'title': s.title, 'user': s.author.name, 'created': s.created, 'subreddit': s.subreddit.display_name, 'id': s.id})
        filenames.add(s.id)
        

    contents = os.listdir('.')
    keepfiles = set()
    count = 0
    for filename in sorted(contents):
        deleteFile = True
        if os.path.isdir(filename):
            continue
        for fname in [f for f in filenames if filename.startswith(f)]:
            count += 1
            keepfiles.add(filename)
            deleteFile = False
            break
        if deleteFile:
            print("- Deleting {}".format(filename))
            os.remove(filename)
    
    print("- Keeping {} files".format(count))
    kept = count

    # remove excluded URLs
    for entry in [entry for entry in to_download if entry['id'] in excluded]:
        print("- Excluding {} ({})".format(entry['id'], unidecode(entry['title'])))
    to_download = [entry for entry in to_download if entry['id'] not in excluded]
    old_excluded = len(excluded)
    excluded = set([entry for entry in excluded if entry in filenames])
    if len(excluded) < old_excluded:
        print("- Removed {} entries from excluded list".format(old_excluded - len(excluded)))
    
    
    count = 0
    downloaded = 0
    for data in to_download:
        if count >= numDownload:
            break
        
        if any([True for f in keepfiles if f.startswith(data['id'])]):
            # already got this file!
            count += 1
            continue

        url = data['url']
       
        # get stupid flickr source if this is a base page
        mode = ''
        unique_id = ''
        old_url = url
        if re.search('[./]flickr.com', url):
            flickr_filename = url.split('/')[-1]
            if '.' not in flickr_filename:
                m = re.search(r'^.*flickr.com/photos/([^/]+)/([^/]+)', url)
                if m and m.group(2) not in ['sets', 'items']:
                    mode = 'flickr'
                    unique_id = m.group(2)
                    url = m.group(0) + '/sizes/k'
       
        response = requests.get(url)
        download_bytes += len(response.content)
        
        # get stupid imgur source if this is a base page
        if re.search('imgur\.com', url):
            imgur_filename = url.split('/')[-1]
            if '.' not in imgur_filename:
                #print response.content
                # we need to get the actual imgur source file
                m = re.search(r'(//i\.imgur\.com/{}\.[^"]+)"'.format(imgur_filename), response.content.decode('utf-8'))
                if m:
                    print("- Encountered imgur redirect: {} -> {}".format(url, m.group(1)))
                    response = requests.get("https:{}".format(m.group(1)))
                    download_bytes += len(response.content)
                else:
                    m = re.search(r'(//i\.imgur\.com/[a-zA-Z0-9]{2,}\.[^"]+)"', response.content.decode('utf-8'))
                    if m:
                        print("- Trying album redirect: {} -> {}".format(url, m.group(1)))
                        response = requests.get("https:{}".format(m.group(1)))
                        download_bytes += len(response.content)
                    else:
                        print("- Could not get imgur redirect for {} ({})".format(url, unidecode(data['title'])))
        if mode == 'flickr':
            m = re.search(r'//[^"]+' + unique_id + r'[^"]+_d\.[^"]+', response.content.decode('utf-8'))
            if m:
                print("- Trying flickr redirect: {} - {}".format(old_url, m.group(0)))
                response = requests.get("https:{}".format(m.group(0)))
                download_bytes += len(response.content)
            else:
                print("- Could not get flickr redirect for {} ({})".format(url, unidecode(data['title'])))


        print("- Downloaded {} ({} - {}) ({} bytes)".format(url, unidecode(data['subreddit']), unidecode(data['title']), len(response.content)))
        sleep(2)

        # edit data
        try:
            bio = io.BytesIO(response.content)
            filename = editImage(bio, data)
            count += 1
            downloaded += 1
            print("- Wrote {} ({})".format(filename, count))
        except Exception as e:
            print("! Error: {}, url={}".format(e, url))
            excluded.add(data['id'])
            bio.close()

    
    print("- {} files total".format(kept + downloaded))
    print("- Downloaded {} bytes total".format(download_bytes))
    with open(dataFile, "wb") as f:
        pickle.dump(excluded, f)
    print("- {} files on exluded list".format(len(excluded)))
    
    

def editImage(bio, data):
    print("- Editing {}".format(data['id']))
    im = Image.open(bio).convert('RGBA')
    
    # resize image
    w,h = im.size
    h_scale = 1080.0 / h
    w_scale = 1920.0 / w
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
    font = ImageFont.truetype('/usr/share/fonts/truetype/roboto/hinted/Roboto-Black.ttf', fontSize)
    timestamp_font = ImageFont.truetype('/usr/share/fonts/truetype/roboto/Roboto-Black.ttf', 12)
    
    txt = data['title']
    txt_before = txt   
 
    # do a little string replacement
    txt = re.sub(r'[\[(]\s*[0-9,]+\s*[xX\u00D7]\s*[0-9,]+\s*[\])]', '', txt, flags=re.UNICODE)
    txt = re.sub(r'[\[(][oO][cCsS][\])]', '', txt)
    txt = re.sub(r' +', ' ', txt)

    timestamp = time.strftime("%m-%d   %H:%M")
    timestamp_w, timestamp_h = draw.textsize(timestamp, timestamp_font)

    if txt != txt_before:
        print("- modified text: {} -> {}".format(unidecode(txt_before), unidecode(txt)))
    
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
    
