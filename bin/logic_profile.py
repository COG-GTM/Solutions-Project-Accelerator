from cProfile import Profile
from functools import wraps
import io
import pstats
try:
    from bin.logic_logger import logging
except ImportError:
    from logic_logger import logging

'''
Example use 

@profile()
def foo():
    print('hello world!')

'''

def profile(sort_args=['cumulative'], print_args=[10]):
    profiler = Profile()

    def decorator(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            profile_result = io.StringIO()
            result = None
            try:
                result = profiler.runcall(fn, *args, **kwargs)
            finally:
                stats = pstats.Stats(profiler,stream=profile_result)
                stats.strip_dirs().sort_stats(*sort_args).print_stats()
                profile_result=profile_result.getvalue()
                print(profile_result)
                logging.info(profile_result)
            return result
        return inner
    return decorator
