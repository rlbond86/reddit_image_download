#!/usr/bin/env python3

from code.config import getConfig, writeConfig
from code.censor import Censor
from code.auth import Auth
from code.submissions import get_submissions, filter_submissions
from code.filesys import try_remove_image
from code.download import download_image
from code.edit import edit_image
from code.database import Database

import praw
import os
import io
import sys
import logging
from time import sleep
import concurrent.futures

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

    db = Database(cp['paths']['database'])
    n = db.delete_very_old_entries(cp.getint('limits','age')+30)
    log.info(f'removed {n} old database entries')
    n = db.exclude_old_entries(cp.getint('limits','age'))
    log.info(f'excluded {n} images due to age')

    files = os.listdir('.')

    fileLimit = cp.getint('limits', 'posts')
    submissions = get_submissions(r, fileLimit, cp)
    
    download_bytes = 0
    valid_urls = []

    for s in filter_submissions(submissions, cp, log):
        username = "[deleted]" if s.author is None else s.author.name
        db.register_image(s.url, s.title, username, s.subreddit.display_name, s.id)
        valid_urls.append(s.url)
    log.info("%d items in download list", len(valid_urls))

    n = db.exclude_missing_urls(valid_urls)
    log.info(f'excluded {n} images due to falling out of top posts')

    untracked = db.get_untracked_files(files)
    n = len(untracked)
    log.info(f'deleting {n} images')
    for filename in untracked:
        try_remove_image(filename)
        log.debug(f'deleted file {filename}')

    cen = Censor(cp)

    download_bytes = 0

    while True:
        next_file = db.get_next_to_download()
        if next_file is None:
            log.info("out of images")
            break

        n = db.get_image_count()
        if n >= cp.getint('limits','images'):
            log.info(f"reached {cp['limits']['images']} images")
            break

        log.debug(f"fetching {next_file['url']}")
        record = {k:next_file[k] for k in next_file.keys()}
        cen.censor_record(record, log)

        responses = download_image(record, log)
        if not responses:
            continue
        download_bytes += sum(len(x.content) for x in responses)
        response = responses[-1]

        # edit data
        try:
            bio = io.BytesIO(response.content)
            filename = edit_image(bio, record, cp, log)
            log.debug("wrote %s (%d)", filename, n+1)
            db.track_image(record['url'], filename)
        except Exception as e:
            log.exception("error: %s, url=%s", e, record['url'])
            log.info(f"excluding {record['url']}")
            db.exclude_url(record['url'])
            bio.close()
            
        # rate limiting
        sleep(cp.getfloat('rate-limit', 'seconds'))
            
    log.info("%d files total", db.get_image_count())
    log.info("downloaded %d bytes total", download_bytes)
    
    
if __name__ == "__main__":
    argv = sys.argv
    if len(argv) < 2:
        argv.append('auth.txt')
    elif len(argv) > 2:
        raise RuntimeError('too many arguments')
    main(argv[1])
    
