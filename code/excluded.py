import pickle

def read_excluded(filename, log):
    excluded_ids = set()
    try:
        with open(filename, 'rb') as f:
            excluded_ids = pickle.load(f)
            log.info("loaded %d excluded files", len(excluded_ids))
    except:
        log.warning("could not load excluded files list")
    return excluded_ids


def write_excluded(filename, excluded, log):
    with open(filename, "wb") as f:
        pickle.dump(excluded, f)
    log.info("%d files on exluded list", len(excluded))


def remove_excluded(to_download, excluded_ids, log):
    for entry in [entry for entry in to_download if entry['id'] in excluded_ids]:
        log.info("excluded id %s", entry['id'])
    new_to_download = [entry for entry in to_download if entry['id'] not in excluded_ids]
    old_excluded = len(excluded_ids)
    filenames = set([entry['id'] for entry in to_download])
    new_excluded = set([entry for entry in excluded_ids if entry in filenames])
    if len(excluded_ids) < old_excluded:
        log.info("removed %d entries from excluded list", old_excluded - len(excluded))
    # replace by reference
    to_download.clear()
    to_download.extend(new_to_download)
    excluded_ids.clear()
    excluded_ids.update(new_excluded)
    
