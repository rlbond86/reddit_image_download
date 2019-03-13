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
