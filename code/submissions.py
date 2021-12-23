import re
import time
from urllib.parse import urlparse

def get_submissions(r, fileLimit, cp):
    mreddit = r.multireddit(cp['multireddit']['user'], cp['multireddit']['multi'])
    submissions = mreddit.hot(limit=fileLimit)
    return submissions

_url_exclusions = {
    'cross-post': r"reddit\.com/r",
    'non-file': r"/$",
    'gif': r"\.gifv?$"
}
_domain_exclusions = r"[.^](gfycat|youtube)\.com$|^v\.redd\.it$|^$"


def filter_submissions(subs, cp, log):
    domain_exclusion_regex = re.compile(_domain_exclusions)
    url_exclusion_regexes = {k:re.compile(v) for k,v in _url_exclusions.items()}

    for s in subs:
        url = s.url
        log.debug("submission %s: %s %s", s.id, url, s.title)
        domain = urlparse(url).hostname
        if domain is None or domain_exclusion_regex.search(domain):
            log.debug("domain %s excluded; skipping", domain)
            continue
        
        if s.over_18:
            log.debug("over 18 content")
            if not cp.getboolean('allow', 'over18'):
                log.debug("over 18; skipping")
                continue
        
        if s.selftext_html is not None:
            log.debug("self post; skipping")
            continue
        
        for reason,regex in url_exclusion_regexes.items():
            if regex.search(url):
                log.debug("url excluded: %s; skipping", reason)
                continue;
        
        if url == '':
            log.warning("blank URL; skipping");
            continue

        log.debug("passed filters")
        yield s
