import os

def try_remove_image(filename):
    try:
        os.remove(filename)
    except IsADirectoryError:
        pass
    except FileNotFoundError:
        pass


def delete_stale_images(filenames_to_download, dataFile, log):
    log.info("examining existing files")
    contents = os.listdir('.')
    keepfiles = set()
    for filename in sorted(contents):
        deleteFile = True
        if os.path.isdir(filename):
            continue
        if filename == dataFile:
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
    return keepfiles
