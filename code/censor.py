from profanityfilter import ProfanityFilter
from copy import deepcopy
import concurrent.futures

_censors = {False: ProfanityFilter(no_word_boundaries=True),
            True:  ProfanityFilter(no_word_boundaries=False)}

def censor_records(records_old, cp, log):
    for k,pf in _censors.items():
        # remove two-letter words
        pf.remove_word('fu')
        pf.remove_word('sx')
    
    records = deepcopy(records_old)
    categories = ('title', 'user', 'subreddit')
    for k in categories:
        section = '{}-language-filter'.format(k)
        if cp.getboolean(section, 'filter'):
            pf = _censors[cp.getboolean(section, 'wholeword')]
            censor_char = cp[section]['character']
            if censor_char == 'erase':
                censor_char = ''
            pf.set_censor(censor_char)
            old_text = [record[k] for record in records]
            new_text = []
            with concurrent.futures.ProcessPoolExecutor() as executor:
                for out in executor.map(pf.censor, old_text):
                    new_text.append(out)
            for old, new, record in zip(old_text, new_text, records):
                if old != new:
                    record[k] = new
                    log.info("censored %s from '%s' to '%s'", k, old, new)
    return records
