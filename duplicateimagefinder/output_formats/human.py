from types import *
import sys

import base


class HumanFormat(base.BaseFormatter):
    def output(self, data):
        assert type(data) is ListType, "data is not a list"

        if not len(data):
            print "No results."
            return

        # List the images that are similar to each other
        for similar in data:
            assert isinstance(similar, base.OutputRecord), "record is not instance of OutputRecord"
            sys.stdout.old_write("%s is %d%% similar to %s\n" % (
                similar.image1, similar.similarity_pct, similar.image2
            ))
            sys.stdout.flush()
