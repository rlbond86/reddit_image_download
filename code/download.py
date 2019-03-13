from urllib.parse import urlparse
import requests
import re

def download_image(data, log):
    url = data['url']
    domain = urlparse(url).hostname
    
    if domain is None:
        return []
    
    response = []
    if re.search(r'[^./]flickr\.com', domain):
        response = _download_flickr(url, log)
    elif re.search(r'[^./]imgur.com', domain):
        response = _download_imgur(url, log)
        
    if not response:
        response = _download_default(url, log)
        
    download_bytes = sum(len(x.content) for x in response)
        
    log.info("downloaded %s (%s - %s) (%d bytes)", url, data['subreddit'], data['title'], download_bytes)
    return response

def _download_flickr(url, log):
    
    # get flickr source if this is a base page
    redirected = False
    unique_id = ''
    flickr_filename = url.split('/')[-1]
    if '.' not in flickr_filename:
        m = re.search(r'^.*flickr.com/photos/([^/]+)/([^/]+)', url)
        if m and m.group(2) not in ['sets', 'items']:
            redirected = True
            unique_id = m.group(2)
            url = m.group(0) + '/sizes/k'
            log.debug("new url %s", url)

    response = [requests.get(url)]

    if redirected:
        m = re.search(r'//[^"]+' + unique_id + r'[^"]+_d\.[^"]+', response[0].content.decode('utf-8'))
        if m:
            log.debug("trying flickr redirect: %s -> %s", old_url, m.group(0))
            response.append(requests.get("https:{}".format(m.group(0))))
        else:
            log.info("could not get flickr redirect for %s (%s)", url, data['title'])

    return response

def _download_imgur(url, log):
    
    response = [requests.get(url)]
    
    # get imgur source if this is a base page
    imgur_filename = url.split('/')[-1]
    if '.' not in imgur_filename:
        # we need to get the actual imgur source file
        m = re.search(r'(//i\.imgur\.com/{}\.[^"]+)"'.format(imgur_filename), response[0].content.decode('utf-8'))
        if m:
            log.debug("encountered imgur redirect: %s -> %s}", url, m.group(1))
            response.append(requests.get("https:{}".format(m.group(1))))
        else:
            m = re.search(r'(//i\.imgur\.com/[a-zA-Z0-9]{2,}\.[^"]+)"', response[0].content.decode('utf-8'))
            if m:
                log.debug("trying album redirect: %s -> %s", url, m.group(1))
                response.append(requests.get("https:{}".format(m.group(1))))
            else:
                log.info("could not get imgur redirect for %s (%s)", url, data['title'])

    return response

def _download_default(url, log):
    
    return [requests.get(url)]
    
