from profanityfilter import ProfanityFilter
from copy import deepcopy
import concurrent.futures

class Censor:
    def __init__(self, cp):
        censors = {False: ProfanityFilter(no_word_boundaries=True),
                   True:  ProfanityFilter(no_word_boundaries=False)}
        twoLetterWords = [item for item in censors[False]._censor_list if len(item) <= 2]

        for k,pf in censors.items():
            for word in twoLetterWords:
                try:
                    pf.remove_word(word)
                except ValueError:
                    pass
        
        self._censors = {}
        for cat in ('title', 'user', 'subreddit'):
            section = f'{cat}-language-filter'
            if cp.getboolean(section, 'filter'):
                self._censors[cat] = censors[cp.getboolean(section, 'wholeword')]
                censor_char = cp[section]['character']
                if censor_char == 'erase':
                    censor_char = ''
                self._censors[cat].set_censor(censor_char)


    def censor_record(self, record, log):
        for k,pf in self._censors.items():
            new_text = pf.censor(record[k])
            if new_text != record[k]:
                log.info(f"censored {k} from '{record[k]}' to '{new_text}'")
                record[k] = new_text
