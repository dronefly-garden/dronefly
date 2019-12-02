"""Module for common code."""
from functools import wraps
from itertools import zip_longest
import logging

LOG = logging.getLogger("red.dronefly.inatcog")


def make_decorator(function):
    """Make a decorator that has arguments."""

    @wraps(function)
    def wrap_make_decorator(*args, **kwargs):
        if len(args) == 1 and (not kwargs) and callable(args[0]):
            # i.e. called as @make_decorator
            return function(args[0])
        # i.e. called as @make_decorator(*args, **kwargs)
        return lambda wrapped_function: function(wrapped_function, *args, **kwargs)

    return wrap_make_decorator


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)
