"""Explicit, versioned scoring; reference text never goes to the model."""
import unicodedata

NORMALIZATION = "nfkc-casefold-punctuation-to-space-v1"


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    return " ".join("".join(
        " " if unicodedata.category(c).startswith("P") and c != "'" else c
        for c in text
    ).split())


def score(reference, hypothesis):
    """Minimum word edit distance, with deterministic S/D/I tie breaking.

    Numbers are intentionally not verbalized; accents and apostrophes are kept.
    Corpus WER must be calculated from summed counts, not averaged sample WERs.
    """
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    if not ref:
        raise ValueError("Transcript chuẩn không có từ để chấm.")
    if len(ref) > 3000 or len(hyp) > 6000:
        raise ValueError("Mẫu quá dài để chấm: tối đa 3.000 từ chuẩn / 6.000 từ dự đoán.")
    # Each entry is (total edits, substitutions, deletions, insertions).
    previous = [(j, 0, 0, j) for j in range(len(hyp) + 1)]
    for i, word in enumerate(ref, 1):
        current = [(i, 0, i, 0)]
        for j, other in enumerate(hyp, 1):
            if word == other:
                current.append(previous[j - 1])
            else:
                a, b, c = previous[j - 1], previous[j], current[j - 1]
                candidates = [(a[0]+1, a[1]+1, a[2], a[3]),
                              (b[0]+1, b[1], b[2]+1, b[3]),
                              (c[0]+1, c[1], c[2], c[3]+1)]
                current.append(min(candidates, key=lambda x: x[0]))
        previous = current
    edits, substitutions, deletions, insertions = previous[-1]
    # Bit-parallel Levenshtein for CER: avoids a quadratic Python character loop.
    ref_chars, hyp_chars = ''.join(ref), ''.join(hyp)
    char_edits = character_distance(ref_chars, hyp_chars)
    return {"wer": edits / len(ref), "errors": edits, "reference_words": len(ref),
            "cer": char_edits / len(ref_chars), "character_errors": char_edits,
            "reference_characters": len(ref_chars),
            "substitutions": substitutions, "deletions": deletions, "insertions": insertions,
            "normalized_reference": " ".join(ref), "normalized_hypothesis": " ".join(hyp)}


def character_distance(reference, hypothesis):
    """Myers bit-vector edit distance; Unicode code points, spaces excluded by caller."""
    if not reference:
        return len(hypothesis)
    masks = {}
    for i, char in enumerate(reference):
        masks[char] = masks.get(char, 0) | (1 << i)
    positive, negative, distance = ~0, 0, len(reference)
    last = 1 << (len(reference) - 1)
    for char in hypothesis:
        equal = masks.get(char, 0)
        xv = equal | negative
        xh = (((equal & positive) + positive) ^ positive) | equal
        ph = negative | ~(xh | positive)
        mh = positive & xh
        distance += bool(ph & last) - bool(mh & last)
        ph = (ph << 1) | 1
        mh <<= 1
        positive = mh | ~(xv | ph)
        negative = ph & xv
    return distance

