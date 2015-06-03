import fnmatch
from multiprocessing import Lock
import os
import signal
import sys


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
    """
    Progress printer
    """
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
