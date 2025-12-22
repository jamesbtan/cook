from functools import wraps


class InvalidToolCall(Exception):
    pass


def call_limit(limit):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            nonlocal limit
            if limit == 0:
                raise InvalidToolCall("Hit call limit")
            limit -= 1
            return f(*args, **kwargs)

        return wrapper

    return decorator


def unique_args(f):
    past_args = set()

    @wraps(f)
    def wrapper(*args, **kwargs):
        hashable_args = (tuple(args), tuple(sorted(kwargs.items())))
        if hashable_args in past_args:
            raise InvalidToolCall("Calling with same args")
        else:
            past_args.add(hashable_args)
        return f(*args, **kwargs)

    return wrapper
