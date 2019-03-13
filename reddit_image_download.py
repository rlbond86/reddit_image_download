#!/usr/bin/env python3

from code.config import getConfig, writeConfig
from code.auth import Auth
from code.excluded import read_excluded, write_excluded, remove_excluded
from code.submissions import get_submissions, filter_submissions
from code.filesys import delete_stale_images
from code.download import download_image
from code.edit import edit_image

import praw
import os
import io
import sys
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
            filename = edit_image(bio, data, cp, log)
            count += 1
            downloaded += 1
            log.debug("wrote %s (%d)", filename, count)
        except Exception as e:
            log.exception("error: %s, url=%s", e, s.url)
            excluded.add(data['id'])
            bio.close()
            
    log.info("%d files total", len(keepfiles) + downloaded)
    log.info("downloaded %d bytes total", download_bytes)
    write_excluded(dataFile_, excluded, log)
    
    
if __name__ == "__main__":
    argv = sys.argv
    if len(argv) < 2:
        argv.append('auth.txt')
    elif len(argv) > 2:
        raise RuntimeError('too many arguments')
    main(argv[1])
    
