from __future__ import print_function

import json
import sys
from urllib2 import urlopen, HTTPError
import md5
import itertools
import os
import subprocess
import shutil
import threading
import time
import tempfile
from argparse import ArgumentParser
import pprint

MAX_RETRIES = 5
BLOCK_SIZE = 10 * 1024 * 1024

def stream_to_file(to_file_name, from_file_obj):
    fd, tmpfile_name = tempfile.mkstemp(dir = os.path.dirname(to_file_name))
    print("to", tmpfile_name)
    try:
        while 1:
            block = from_file_obj.read(BLOCK_SIZE)
            if not block:
                break
            os.write(fd, block)
    finally:
        os.close(fd)
        os.rename(tmpfile_name, to_file_name)

process_exit_code = 0


def fetch_url(url, tgt):
    retries = MAX_RETRIES
    global process_exit_code
    while 1:

        try:
            content = urlopen(url)
        except HTTPError,e:
            if e.code >= 500:
                retries -= 1
                print("Fail", url, "retry", retries, e)
                if retries <= 0:
                    raise e
                time.sleep(5)
                continue
            else:
                process_exit_code = 1
                raise
        stream_to_file(tgt, content)
        break


def file_name_from_url(url):
    hash = md5.md5(url).hexdigest()
    fpart = "".join(ch for ch in url.rsplit("/")[-1] if ch.isalnum())
    return hash + "_" + fpart

def unzip_to(fname, tgt):
    subprocess.check_call(["unzip",  "-o", "-q", fname, "-d", tgt])

def path_from_config(config,path):
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(config['root'], path))

def run_exe(target_path, args):
    parts = [target_path] + args
    print(">", target_path, args)
    subprocess.check_call(parts)

def handle_fetch(fetch, config):
    url = fetch['url']
    fname = file_name_from_url(url)
    archive_dir = path_from_config(config, config['archive'])
    targetpath = os.path.join(archive_dir, fname)
    if not os.path.isfile(targetpath):
        fetch_url(url, targetpath)
    ziptarget = fetch.get('unzipTo')
    if ziptarget:
        unzip_to(targetpath, path_from_config(config, ziptarget))
    saveTarget = fetch.get("saveAs")
    if saveTarget:
        shutil.copy(targetpath, path_from_config(config, saveTarget))
    runargs = fetch.get("runWithArgs")
    if runargs:
        run_exe(targetpath, runargs)

def created_temp_dir():
    """ creates archive directory in temp (used of none of specified exist) """
    pth = os.path.join(tempfile.gettempdir(), "zipget")
    if not os.path.isdir(pth):
        print("Warning: none of archive dirs existed, creating", pth)
        os.makedirs(pth)
    return pth

def accept_frag(frag, tags):
    # user didn't specify tags -> install everything
    if not tags:
        return True

    if not frag.get('tags'):
        return False
    # user specified tags -> install only if overlapping tags
    return len(set(tags).intersection(set(frag['tags']))) > 0

def handle_recipe(fname, args):
    r = json.load(open(fname))

    config = {
        "root": os.path.abspath(os.path.dirname(fname))
    }
    archive_dirs = r['config']['archive']
    archive_tries = [f for f in archive_dirs if os.path.isdir(path_from_config(config, f) )]
    if len(archive_tries) == 0:
        archive = created_temp_dir()
    else:
        archive = archive_tries[0]

    config['archive'] = path_from_config(config, archive)
    threads = []
    frags = [frag for frag in r['fetch'] if accept_frag(frag, args.tags)]
    if args.v:
        pprint.pprint(config)
        pprint.pprint(frags)
    for frag in frags:
        t = threading.Thread(target=handle_fetch, args=(frag, config))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if process_exit_code > 0:
        print("Zipget failed with exit code", process_exit_code)
        sys.exit(process_exit_code)

def main(args):
    """ Handle and dispatch args. Can be used as 'api' """
    p = ArgumentParser()
    p.add_argument('recipe', nargs=1, help="Recipe (json) file to run")
    p.add_argument('tags', nargs="*", metavar="tag", help="Tags for parts of recipe to run")
    p.add_argument('-v', action="store_true", help="Verbose output")
    parsed = p.parse_args(args)
    recipe = parsed.recipe[0]
    handle_recipe(recipe, parsed)

if __name__ == "__main__":
    main(sys.argv[1:])