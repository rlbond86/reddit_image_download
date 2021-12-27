from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
import time
import re

def edit_image(bio, data, cp, log):
    log.info("editing %s", data['postcode'])
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
    filename = data['postcode'] + '.jpg'
    rgb_result.save(filename, quality=100)
    bio.close()
    return filename
