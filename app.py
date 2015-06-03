#!/usr/bin/env python

import argparse
import fnmatch
from functools import partial
from multiprocessing import Pool, Lock, cpu_count
import os
import signal
import sys
import time

from blitzdb import FileBackend, Document
from PIL import Image
from tqdm import *

from __init__ import *


class ImageHash(Document):
    pass


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
    sys.stdout.old_write('\r[{0}{1}] {2}% {3} {4} {5}'.format('#'*bars_done, '-'*bars_not_done, progress, rate_str, eta_str, ' '*10))
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

    # In-memory hashes that we've encountered during the scan
    saved_hashes = dict()

    backend_lock = Lock()
    persistent_store = FileBackend("hashes.db")
    persistent_store.create_index(ImageHash, 'name')

    @classmethod
    def lookup_file(cls, filename):
        """
        Check the database for images with this file path
        """
        try:
            return cls.persistent_store.get(ImageHash, {'name': filename})
        except ImageHash.DoesNotExist:
            pass
        except ImageHash.MultipleDocumentsReturned:
            cls.persistent_store.delete(ImageHash({'name': filename}))
            raise
        return None

    @classmethod
    def save_hash(cls, key, value):
        """
        Saves a json record of image file path to it's hash and the last modified date of the image.

        Since this method gets called in the parent thread as a callback to when workers finish calculating a
        hash, we have no way of knowing whether it is new or not so this method checks the last modified time
        stamp and only does the save if it is stale.
        """

        current_mtime = os.stat(key).st_mtime
        should_save_record = True

        # Delete existing record if it exist because file based db doesn't support updating
        i = cls.lookup_file(key)
        if i:
            if i.created != current_mtime:
                cls.persistent_store.delete(i)
            else:
                should_save_record = False

        # Save new record
        if should_save_record:
            r = ImageHash({'name': key, 'hash': value, 'created': os.stat(key).st_mtime})
            cls.backend_lock.acquire()
            cls.persistent_store.save(r)
            cls.backend_lock.release()

        cls.saved_hashes[key] = value

    @classmethod
    def hash(cls, image, filename=None):
        # Return already calculated hash in memory
        if cls.saved_hashes.get(filename, None):
            return cls.saved_hashes.get(filename, None)
        # Return already calculated hash in db
        i = cls.lookup_file(filename)
        if i:
            # Check if image has not been modified since last hash
            if i.created >= os.stat(filename).st_mtime:
                return i.hash
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
    worker_pool = Pool(processes=cpus, initializer=init_worker, maxtasksperchild=100)
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
        done, elapsed, total, started = 0, 0, len(worker_results), time.time()
        worker_pool.close()
        while True:
            done = sum(r.ready() for r in worker_results)
            elapsed = time.time() - started
            rate = int(done / elapsed)
            eta = int((total - done) / float(rate)) if done > 0 else None
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
        ImageUtils.persistent_store.commit()
        exit(1)
    else:
        worker_pool.join()
        ImageUtils.persistent_store.commit()

    # Comparison
    print ""
    print "Comparing the images..."

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
        'cpus': cpu_count(),
    }
    locals().update(defaults)

    parser = argparse.ArgumentParser(description=__summary__)

    parser.add_argument('-c', '--confidence', dest='confidence_threshold', type=int,
                        help='at what percent (1-100) similarity should photos be flagged (default {})'.format(
                            defaults['confidence_threshold']))
    parser.add_argument('--cpus', type=int,
                        help='override number of cpu cores to use, default is to utilize all of them (default {})'.format(
                            defaults['cpus']
                        ))
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
    if args.cpus:
        cpus = args.cpus

    main(**locals())

    exit(0)
