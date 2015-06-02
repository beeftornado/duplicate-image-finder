#!/usr/bin/env python

import argparse
import fnmatch
from functools import partial
from multiprocessing import Pool, Lock, cpu_count
import os
import signal
import sys
import time

from PIL import Image
from tqdm import *

from __init__ import *


def hijack_print():
    """
    Makes the built in print safe for use by multiple processes
    """
    stdout_lock = Lock()

    from datetime import datetime as dt

    old_f = sys.stdout

    class F:
        nl = True

        def old_write(self, x):
            old_f.write(x)

        def write(self, x):
            stdout_lock.acquire()
            if not x or x == '\n' or x == '' or len(x) == 0:
                old_f.write(x)
                self.nl = True
            else:
                old_f.write('%s> %s' % (str(dt.now()), x))
                self.nl = False
            stdout_lock.release()

        def flush(self):
            old_f.flush()

    sys.stdout = F()


def init_worker():
    """
    Ignores Ctrl-C in workers so parent can kill pool
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def print_progress(progress, rate=None, eta=None):
    bars_to_show = 10
    divisor = 100 / bars_to_show
    bars_done = progress / divisor
    bars_not_done = bars_to_show - bars_done
    rate_str = '({} per second)'.format(rate) if rate else ''
    eta_str = '({}:{} remaining)'.format(eta/60, str(eta%60).zfill(2)) if eta != None else ''
    sys.stdout.old_write('\r[{0}{1}] {2}% {3} {4}  '.format('#'*bars_done, '-'*bars_not_done, progress, rate_str, eta_str))
    sys.stdout.flush()
    if progress >= 100:
        print ""


def osx_photoslibrary_location():
    """
    Find the OSX Photos.app library location. Don't assume everyone uses default naming.
    """
    pictures_home = os.path.expanduser("~/Pictures/")
    libraries = []
    for root, dirnames, filenames in os.walk(pictures_home):
        for dirname in fnmatch.filter(dirnames, '*.photoslibrary'):
            libraries.append(os.path.join(root, dirname))
    if not len(libraries):
        print "Apple Photos library not found."
        exit(1)
    if len(libraries) > 1:
        # Found more than one library
        print 'Found {} photos libraries, which one do you want to use?'.format(len(libraries))
        opt_idx = 1
        for l in libraries:
            print '{}. {}'.format(opt_idx, l)
        print ''
        choice = raw_input(" >>  ")
        libraries[0] = libraries[choice-1]
    return libraries[0]


class MethodProxy(object):
    """
    Allows class methods to be used as multiprocessing pool targets since they are normally not picklable
    """
    def __init__(self, obj, method):
        self.obj = obj
        if isinstance(method, basestring):
            self.methodName = method
        else:
            assert callable(method)
            self.methodName = method.func_name

    def __call__(self, *args, **kwargs):
        return getattr(self.obj, self.methodName)(*args, **kwargs)


class ImageUtils(object):
    saved_hashes = dict()

    @classmethod
    def save_hash(cls, key, value):
        cls.saved_hashes[key] = value

    @classmethod
    def hash(cls, image, filename=None):
        # Return already calculated hash
        if cls.saved_hashes.get(filename, None):
            return cls.saved_hashes.get(filename, None)
        if not isinstance(image, Image.Image):
            # Check if file is an image
            try:
                image = Image.open(image)
            except IOError:
                return None
        image = image.resize((8, 9), Image.ANTIALIAS).convert('L')
        avg = reduce(lambda x, y: x + y, image.getdata()) / 64.
        avhash = reduce(lambda x, (y, z): x | (z << y),
                        enumerate(map(lambda i: 0 if i < avg else 1, image.getdata())),
                        0)
        cls.saved_hashes[filename] = avhash
        return avhash

    @staticmethod
    def hamming_score(hash1, hash2):
        h, d = 0, hash1 ^ hash2
        while d:
            h += 1
            d &= d - 1
        return h


def main(*args, **kwargs):
    """
    Main program
    """
    locals().update(kwargs)

    # Format the print messages and make it thread safe
    hijack_print()

    # Identified pairs of related images
    similar_pairs = list()

    # Find all files under directory
    images = []
    for root, dirnames, filenames in os.walk(start_dir):
        for filename in fnmatch.filter(filenames, '*.*'):
            images.append(os.path.join(root, filename))

    file_count = len(images)
    print "%d files to process in %s" % (file_count, start_dir)

    if file_count == 0:
        print "No images found"
        exit(0)

    # Prehash
    print "Please wait for initial image scan to complete..."

    # Create a worker pool to hash the images over multiple cpus
    worker_pool = Pool(processes=cpu_count(), initializer=init_worker, maxtasksperchild=100)
    worker_results = []

    # Cache all the image hashes ahead of time so user can see progress
    for idx, image_path in enumerate(images):

        # Don't process last image as it will not have anything to compare against
        if idx < file_count:
            new_callback_function = partial(lambda x, key: ImageUtils.save_hash(key, x), key=image_path)
            worker_results.append(worker_pool.apply_async(MethodProxy(ImageUtils, ImageUtils.hash), [image_path, image_path],
                                    callback=new_callback_function))

    # This block basically prints out the progress os hashing is done and allows graceful exit if user quits
    try:
        done, elapsed, total, started = 0, 0, len(worker_results), time.clock()
        worker_pool.close()
        while True:
            done = sum(r.ready() for r in worker_results)
            elapsed = time.clock() - started
            rate = int((done / elapsed) / 1000)
            eta = int((total - done) / ((done / elapsed) / 1000)) if done > 0 else None
            print_progress(int(float(done)/total*100), rate, eta)
            # if all(r.ready() for r in worker_results):
            if done == total:
                print "Hashing completed"
                break
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print '\n'
        print "Caught KeyboardInterrupt, terminating workers"
        worker_pool.terminate()
        worker_pool.join()
        exit(1)
    else:
        worker_pool.join()

    # Comparison
    print ""
    print "LOOKING FOR DUPLICATES:"

    # Compare each image to every other image
    for idx, image_path in enumerate(tqdm(images)):

        # Don't process last image as it will not have anything to compare against
        if idx == file_count - 1:
            continue

        hash1 = ImageUtils.hash(image_path, image_path)

        if not hash1:
            continue

        # Compare to all images following
        for image_path2 in images[idx + 1:]:

            # Skip same image paths if it happens
            if image_path == image_path2:
                continue

            hash2 = ImageUtils.hash(image_path2, image_path2)

            if not hash2:
                continue

            # Compute the similarity values
            dist = ImageUtils.hamming_score(hash1, hash2)
            similarity = (64 - dist) * 100 / 64

            if similarity > confidence_threshold:
                similar_pairs.append([image_path, image_path2, dist, similarity])

    # List the images that are similar to each other
    for similar in similar_pairs:
        print "%s is %d%% similar to %s" % (
            similar[0], similar[3], similar[1]
        )

    print ""


if __name__ == '__main__':

    defaults = {
        'confidence_threshold': 90,
        'start_dir': '.',
    }
    locals().update(defaults)

    parser = argparse.ArgumentParser(description=__summary__)

    parser.add_argument('-c', '--confidence', dest='confidence_threshold', type=int,
                        help='at what percent (1-100) similarity should photos be flagged (default {})'.format(
                            defaults['confidence_threshold']))
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-d', '--directory', dest='start_dir', type=str,
                       help='folder to start looking for photos')
    group.add_argument('--osxphotos',
                       help='scan the Photos app library on Mac', action='store_true')

    args = parser.parse_args()
    if args.confidence_threshold:
        confidence_threshold = args.confidence_threshold
    if args.start_dir:
        start_dir = args.start_dir
    if args.osxphotos:
        start_dir = os.path.expanduser("{}/Masters/".format(osx_photoslibrary_location()))

    main(**locals())

    exit(0)
