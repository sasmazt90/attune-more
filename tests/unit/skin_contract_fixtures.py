"""Synthetic observations for photometric unit contracts, never camera evidence.

The measured neutral-expression prerequisite was added after these numerical
fold/edge tests. Supply it explicitly so they still exercise their intended
photometric boundary. Missing/stale observations have separate negative tests.
"""
import instant_appearance
from skin_expression import REQUIRED, VERSION


def observed_neutral_proxy(*args, **kwargs):
    if args[3] in ('chin', 'rightCheek', 'leftCheek'):
        photo_id = kwargs.setdefault('photo_id', 'a' * 64)
        kwargs.setdefault('expression_observation', {
            'version': VERSION, 'photoId': photo_id,
            'scores': {key: .01 for key in REQUIRED},
        })
    return instant_appearance.instant_proxy(*args, **kwargs)
