from types import *
import json
import sys

import base


class JsonFormat(base.BaseFormatter):
    def output(self, data):
        assert type(data) is ListType, "data is not a list"

        # List the images that are similar to each other
        sys.stdout.old_write('[')
        for similar in data:
            assert isinstance(similar, base.OutputRecord), "record is not instance of OutputRecord"
            sys.stdout.old_write(json.dumps({'image1': similar.image1, 'image2': similar.image2,
                              'similarity': similar.similarity_pct}) + ',')
            sys.stdout.flush()
        sys.stdout.old_write(']')
