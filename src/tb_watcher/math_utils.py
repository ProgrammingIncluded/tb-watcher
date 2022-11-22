"""
Basic Python implementation of math functions.
By: ProgrammingIncluded
"""
# We try avoid heavy installations like numpy.
# But if we really need them, we can consider them.

from typing import Callable

def calc_average_percentile(percentage: float) -> Callable:
    """
    Returns a function that returns the average with a given percentile
    """
    def _func(lst):
        if len(lst) < 4:
            return sum(lst) / len(lst)
    
        cut_off = int(len(lst) * percentage)
        s = sorted(lst)[cut_off:len(lst) - cut_off]
        return sum(s) / len(s)

    return _func

def window_average(window: int) -> Callable:
    """Returns a function which calculates a sliding window logic when given a list."""
    def _func(lst):
        v = lst[:-min(window, len(lst))]

        if len(v) == 0:
            return lst[-1]

        return sum(v) / len(v)
    return _func

def constant(const: float) -> Callable:
    """Returns a function which returns a constant."""
    def _func(lst):
        return const
    return _func
