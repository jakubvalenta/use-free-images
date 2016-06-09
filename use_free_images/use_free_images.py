#!/usr/bin/env python

import hashlib
import json
import os
import re
import time
import urllib.parse

import flickrapi
import requests
from bs4 import BeautifulSoup

import listio


DIR_CACHE_HTML = 'html'
DIR_CACHE_PHOTOS = 'photos'

HEADERS = {
    'User-Agent':
    'Mozilla/5.0 (X11; Linux x86_64; rv:46.0) Gecko/20100101 Firefox/46.0',
    'Accept':
    'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.5',
    'DNT': '1',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
}

REGEX_FREEIMAGES_PHOTO = re.compile(
    '^http:\/\/www\.freeimages\.com\/photo\/[^\/]+$'
)
REGEX_MORGUEFILE_PHOTO = re.compile(
    '^http:\/\/morguefile\.com\/p\/\d+$'
)
REGEX_FLICKR_PHOTO = re.compile(
    '^https:\/\/www\.flickr\.com\/photos\/[^\/]+\/\d+\/$'
)
REGEX_FLICKR_USER = re.compile(
    '^https:\/\/www\.flickr\.com\/photos\/[^\/]+\/$'
)
REGEX_FLICKR_USER_ID = re.compile('^\d+@N\d+$')

FLICKR_LIMIT = 500
FLICKR_TIMEOUT = 2

FREEIMAGE_TIMEOUT = 60

flickr = None


def download_page(url):
    print('Downloading {}'.format(url))
    headers = HEADERS.copy()
    parsed = urllib.parse.urlsplit(url)
    base_url = '{}://{}/'.format(parsed.scheme, parsed.hostname)
    headers['Referer'] = base_url
    r = requests.get(url, headers=HEADERS)
    if r.status_code != requests.codes.ok or not r.content:
        print('HTTP error {} {}'.format(r.status_code, r.text))
        return None
    return r.text


def cache_create_dir(id, dir_cache):
    path_cache = os.path.join(dir_cache, id)
    if not os.path.isdir(dir_cache):
        os.makedirs(dir_cache)
    return path_cache


def cache_read(id, dir_cache):
    path_cache = cache_create_dir(id, dir_cache)
    if os.path.isfile(path_cache):
        print('Reading cache {}'.format(path_cache))
        with open(path_cache, 'r') as f:
            return f.read()


def cache_write(id, dir_cache, data):
    path_cache = cache_create_dir(id, dir_cache)
    print('Writing cache {}'.format(path_cache))
    with open(path_cache, 'w') as f:
        print(data, file=f)
        return data


def download_page_with_cache(url, dir_cache):
    id = hashlib.sha256(str(url).encode()).hexdigest()[0:16]
    html = cache_read(id, dir_cache)
    if not html:
        html = download_page(url)
        if html:
            cache_write(id, dir_cache, html)
    return html


def parse_html_freeimage_photo(html):
    print('Parsing FreeImages')
    soup = BeautifulSoup(html, 'html.parser')
    if soup.title.string == 'Are you human? - FreeImages.com':
        print('Error captcha')
        return
    img = soup.select('.preview > img')[0]
    photo_url = img['src']
    author = soup.find(id='photographer-name').string
    photo = {
        'url': photo_url,
        'copyright': 'FreeImages.com / {}'.format(author)
    }
    return photo


def parse_html_morguefile_photo(html):
    print('Parsing MorgueFile')
    soup = BeautifulSoup(html, 'html.parser')
    img = soup.select('.img-responsive')[0]
    photo_url = img['src']
    author_link = soup.select('.creative > a')[0]
    author = author_link['href'].split('/')[-1]
    photo = {
        'url': photo_url,
        'copyright': 'MorgueFile / {}'.format(author)
    }
    return photo


def flickr_connect(api_key, api_secret):
    global flickr
    if flickr is None:
        flickr = flickrapi.FlickrAPI(api_key, api_secret)
    return flickr


def flickr_read_photo_obj(flickr, photo_id):
    raw = flickr.photos.getInfo(photo_id=photo_id, format='json')
    parsed = json.loads(raw.decode('utf-8'))
    # print(parsed)
    p = parsed['photo']
    if p['owner']['realname']:
        author = p['owner']['realname']
    else:
        author = p['owner']['username']
    return {
        'id': p['id'],
        'secret': p['secret'],
        'farm_id': p['farm'],
        'server_id': p['server'],
        'author': author
    }


def flickr_read_user_name(flickr, user_id):
    raw = flickr.people.getInfo(user_id=user_id, format='json')
    parsed = json.loads(raw.decode('utf-8'))
    # print(parsed)
    p = parsed['person']
    if p['realname'] and p['realname']['_content']:
        name = p['realname']['_content']
    else:
        name = p['username']
    return name


def flickr_read_user_photos_obj(flickr, user_id):
    raw = flickr.people.getPhotos(user_id=user_id, limit=FLICKR_LIMIT,
                                  format='json')
    parsed = json.loads(raw.decode('utf-8'))
    # print(parsed)
    for p in parsed['photos']['photo']:
        yield {
            'id': p['id'],
            'secret': p['secret'],
            'farm_id': p['farm'],
            'server_id': p['server'],
            'author': None
        }


def flickr_format_photo_url(photo_obj, size=''):
    if size:
        size_str = '_' + size
    else:
        size_str = ''
    return ('https://farm{farm_id}.staticflickr.com/{server_id}/'
            '{photo_id}_{secret}{size}.jpg'.format(
                photo_id=photo_obj['id'],
                secret=photo_obj['secret'],
                farm_id=photo_obj['farm_id'],
                server_id=photo_obj['server_id'],
                size=size_str
            ))


def flickr_find_user_by_username(flickr, username):
    print('Flickr findByUsername {}'.format(username))
    raw = flickr.people.findByUsername(username=username, format='json')
    parsed = json.loads(raw.decode('utf-8'))
    # print(parsed)
    u = parsed['user']
    return u['nsid']


def process_url_flickr_photo(url, flickr):
    photo_id = url.split('/')[-2]
    print('Flickr Photo ID {}'.format(photo_id))

    photo_obj = flickr_read_photo_obj(flickr, photo_id)

    photo = {
        'url': flickr_format_photo_url(photo_obj),
        'copyright': 'Flickr / {}'.format(photo_obj['author'])
    }
    if FLICKR_TIMEOUT:
        time.sleep(FLICKR_TIMEOUT)
    return [photo]


def process_url_flickr_user(url, flickr):
    user_id_or_name = url.split('/')[-2]
    print('Flickr User {}'.format(user_id_or_name))

    if REGEX_FLICKR_USER_ID.match(user_id_or_name):
        user_id = user_id_or_name
    else:
        user_id = flickr_find_user_by_username(flickr, user_id_or_name)

    author = flickr_read_user_name(flickr, user_id)

    photos = flickr_read_user_photos_obj(flickr, user_id)
    for photo_obj in photos:
        photo = {
            'url': flickr_format_photo_url(photo_obj),
            'copyright': 'Flickr / {}'.format(author)
        }
        yield photo


def process_url_freeimage(url, dir_cache):
    html = download_page_with_cache(url, dir_cache)
    photo = parse_html_freeimage_photo(html)
    if FREEIMAGE_TIMEOUT:
        time.sleep(FREEIMAGE_TIMEOUT)
    if photo:
        return [photo]


def process_url_morguefile(url, dir_cache):
    html = download_page_with_cache(url, dir_cache)
    photo = parse_html_morguefile_photo(html)
    if photo:
        return [photo]


def process_url(url, dir_cache_html, flickr):
    if REGEX_FLICKR_USER.match(url):
        return process_url_flickr_user(url, flickr)
    if REGEX_FREEIMAGES_PHOTO.match(url):
        return process_url_freeimage(url, dir_cache_html)
    if REGEX_MORGUEFILE_PHOTO.match(url):
        return process_url_morguefile(url, dir_cache_html)
    if REGEX_FLICKR_PHOTO.match(url):
        return process_url_flickr_photo(url, flickr)
    print('Unknown URL "{}"'.format(url))


def process_urls(urls, dir_cache_html, dir_cache_photos, flickr):
    for url, copyright_ in urls:
        print(url, copyright_)
        id = hashlib.sha256(str(url).encode()).hexdigest()[0:16]
        data = cache_read(id, dir_cache_photos)
        if data:
            photos = json.loads(data)
        else:
            photos_raw = process_url(url, dir_cache_html, flickr)
            print(photos_raw)
            if not photos_raw:
                continue
            photos = list(photos_raw)
            dump = json.dumps(photos)
            cache_write(id, dir_cache_photos, dump)
        for photo in photos:
            if copyright_:
                photo['copyright'] = copyright_
            yield photo


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description=('Use Free Images: Bulk download URL and copyright '
                     'information about images from Flickr, '
                     'FreeImages.com and MorgueFile')
    )
    parser.add_argument('--input', '-i', dest='urls_file',
                        required=True,
                        help='path to a file with the URLs to download '
                        '(CSV, 1st column: URL, 2nd column: copyright '
                        'info to override the downloaded info')
    parser.add_argument('--cache', '-c', dest='cache_dir',
                        required=True,
                        help='path to a cache directory')
    parser.add_argument('--flickr', '-f', dest='flickr_file',
                        required=True,
                        help='path to a flick credentials file '
                        '(first line API key, second line API secret)')
    parser.add_argument('--output', '-o', dest='output_file',
                        required=True,
                        help='path to a file to write the resulting JSON')
    args = parser.parse_args()

    urls = listio.read_map(args.urls_file)
    dir_cache_html = os.path.join(args.cache_dir, DIR_CACHE_HTML)
    dir_cache_photos = os.path.join(args.cache_dir, DIR_CACHE_PHOTOS)

    flickr_credentials = listio.read_list(args.flickr_file)
    flickr_api_key = flickr_credentials[0]
    flickr_api_secret = flickr_credentials[1]
    flickr = flickr_connect(flickr_api_key, flickr_api_secret)

    photos_gen = process_urls(urls, dir_cache_html, dir_cache_photos, flickr)
    photos = list(photos_gen)
    with open(args.output_file, 'w') as f:
        json.dump(photos, f, indent=2)


if __name__ == '__main__':
    main()
