class BaseFormatter(object):
    pass

class OutputRecord(object):
    image1, image2, hamming_score, similarity_pct = None, None, None, None

    def __init__(self, image1, image2, hamming_score, similarity_pct):
        self.image1 = image1
        self.image2 = image2
        self.hamming_score = hamming_score
        self.similarity_pct = similarity_pct
