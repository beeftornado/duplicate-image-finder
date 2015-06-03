from types import *

import base


class HumanFormat(base.BaseFormatter):
    def output(self, data):
        assert type(data) is ListType, "data is not a list"

        # List the images that are similar to each other
        for similar in data:
            assert isinstance(similar, base.OutputRecord), "record is not instance of OutputRecord"
            print "%s is %d%% similar to %s" % (
                similar.image1, similar.similarity_pct, similar.image2
            )
