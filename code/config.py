from xdg import XDG_CONFIG_HOME
from configparser import ConfigParser
import os
import pathlib

_default_conf = """
[multireddit]
user=kjoneslol
multi=sfwpornnetwork

[limits]
posts=250
images=120
age=7

[processing]
timestamp=yes
title=yes
username=yes
subreddit=yes
width=1920
height=1080

[title-font]
name=/usr/share/fonts/truetype/roboto/hinted/Roboto-Black.ttf
size=28

[timestamp-font]
name=/usr/share/fonts/truetype/roboto/hinted/Roboto-Black.ttf
size=12

[subreddit-language-filter]
filter=yes
character=erase
wholeword=no

[user-language-filter]
filter=yes
character=*
wholeword=no

[title-language-filter]
filter=yes
character=*
wholeword=yes

[allow]
over18=no

[paths]
images=~/reddit_images

[logging]
level=info

[rate-limit]
seconds=2
"""

def getConfigDirectory():
    if XDG_CONFIG_HOME is not None:
        return XDG_CONFIG_HOME
    if os.name == 'nt':
        raise NotImplementedError("Windows default configuration path not implemented")
    return pathlib.PosixPath(os.path.expanduser('~/.config'))
                             
def _confDir(directory):
    if directory is not None:
        return pathlib.Path(os.path.expanduser(directory))
    return getConfigDirectory()

def _confPath(directory, name):
    path = _confDir(directory)

    if name is None:
        name = 'reddit_image_download.conf'
    return path / name

def getConfig(name=None, directory=None, log=None):
    filePath = _confPath(name, directory)
    cp = ConfigParser()
    cp.read_string(_default_conf)
    cp.read(filePath)
    if log is not None:
        log.info("read config file %s", filePath)
    return cp

def writeConfig(cp, name=None, directory=None, log=None):
    fileDir = _confDir(directory)
    filePath = _confPath(name, directory)

    try:
        if not os.path.exists(fileDir):
            os.makedirs(fileDir)
        with open(filePath, 'w') as f:
            cp.write(f)
            if log is not None:
                log.debug("wrote config")
    except:
        if log is not None:
            log.exception("error writing config file")
