import calendar
import re
import time

def get_submissions(r, fileLimit, cp):
    mreddit = r.multireddit(cp['multireddit']['user'], cp['multireddit']['multi'])
    submissions = mreddit.hot(limit=fileLimit)
    return submissions

_url_exclusions = {
    'cross-post': r"reddit\.com/r",
    'non-file': r"/$",
    'gif': r"\.gifv?$"
}
_domain_exclusions = r"[.^](gfycat|youtube)\.com$|^v\.redd\.it$"


def filter_submissions(subs, cp, log):
    domain_regex = re.compile(r"https?://([^/]+)[/$]")
    domain_exclusion_regex = re.compile(_domain_exclusions)
    url_exclusion_regexes = {k:re.compile(v) for k,v in _url_exclusions.items()}
    max_days = cp.getint('limits', 'age')
    max_seconds = max_days * 24*60*60

    for s in subs:
        url = s.url
        log.debug("submission %s: %s %s", s.id, url, s.title)
        m = domain_regex.search(url)
        if m is None:
            log.warning("could not determine domain of %s", url)
            continue;
        domain = m.group(1)
        if domain_exclusion_regex.search(domain):
            log.debug("url excluded; skipping")
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
        
        if calendar.timegm(time.gmtime()) - s.created_utc > max_seconds:
            log.debug("too old; skipping")
            continue
        
        if url == '':
            log.warning("blank URL; skipping");
            continue

        log.debug("passed filters")
        yield s
