#!/usr/bin/env python

import argparse
from functools import partial
from multiprocessing import Pool, cpu_count
import time

from blitzdb import FileBackend, Document
from PIL import Image
from tqdm import *

from __init__ import *
from enums import *
from output_formats import outputter_for_format
from output_formats.base import OutputRecord
from utils import *


class ImageHash(Document):
    pass


class ImageUtils(object):

    # In-memory hashes that we've encountered during the scan
    saved_hashes = dict()

    backend_lock = Lock()
    persistent_store = FileBackend("hashes.db")
    persistent_store.create_index(ImageHash, 'name')

    # For accurate ETA estimates, track how many new hashes were completed
    new_hash_count = 0

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
            cls.new_hash_count += 1

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
            # Don't include any thumbnail or other junk from iPhoto/Photos
            if not '.photoslibrary' in root or 'Masters' in root:
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
            rate = int(ImageUtils.new_hash_count / elapsed)
            eta = int((total - done) / float(rate)) if done > 0 and rate > 0 else None
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

    if only_index:
        return

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
                similar_pairs.append(OutputRecord(image_path, image_path2, dist, similarity))

    # Print the results
    outputter_for_format(output).output(similar_pairs)

    print ""


if __name__ == '__main__':

    defaults = {
        'confidence_threshold': 90,
        'start_dir': '.',
        'cpus': cpu_count(),
        'output': Formats.HUMAN_READABLE,
        'only_index': False,
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
    parser.add_argument('-f', '--format',
                        help='how do you want the list of photos presented to you (human/default, json, csv, table)')
    parser.add_argument('--index',
                       help='only index the photos and skip comparison and output steps', action='store_true')

    args = parser.parse_args()
    if args.confidence_threshold:
        confidence_threshold = args.confidence_threshold
    if args.start_dir:
        start_dir = args.start_dir
    if args.osxphotos:
        start_dir = os.path.expanduser("{}/Masters/".format(osx_photoslibrary_location()))
    if args.cpus:
        cpus = args.cpus
    if args.format:
        output = Formats.from_option(args.format)
    if args.index:
        only_index = args.index

    main(**locals())

    exit(0)
