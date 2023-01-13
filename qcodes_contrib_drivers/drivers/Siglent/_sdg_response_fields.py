from itertools import takewhile
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    Optional,
    Tuple,
    TypeVar,
)

T = TypeVar("T")


def identity(x: T) -> T:
    return x


def group_by_two(list_: Iterable[T]) -> Iterator[Tuple[T, T]]:
    return zip(*2 * (iter(list_),))


def find_first_by_key(
    search_key: str,
    items: Iterable[Tuple[str, str]],
    *,
    transform_found: Callable[[str], Any] = identity,
    not_found=None,
) -> Any:
    for k, value in items:
        if k == search_key:
            return transform_found(value)
    else:
        return not_found


def substr_from(_n, /, *, then=identity) -> Callable[[str], Any]:
    if then is identity:
        return lambda _s: _s[_n:]
    return lambda str: then(str[_n:])


def none_to_empty_str(value):
    return "" if value is None else value


def strip_unit(
    _suffix: str, /, *, then: Callable[[str], Any] = identity
) -> Callable[[str], Any]:
    if then is identity:
        return lambda _s: _s.removesuffix(_suffix)

    return lambda _s: then(_s.removesuffix(_suffix))


def merge_dicts(*dicts: dict) -> dict:
    dest = dict()
    for src in dicts:
        dest.update(src)
    return dest


def extract_standalone_first_field_or_regular_field(
    _result_prefix_len: int,
    /,
    name: Optional[str],
    *,
    then: Callable[[str], Any] = identity,
    else_default=None,
) -> Callable[[str], Any]:

    if name is None:

        def result_func(response: str):
            response_items = iter(response[_result_prefix_len:].split(","))
            first = next(response_items)
            return then(first)

    else:

        def result_func(response: str):
            response_items = iter(response[_result_prefix_len:].split(","))
            next(response_items)
            return find_first_by_key(
                name,
                group_by_two(response_items),
                transform_found=then,
                not_found=else_default,
            )

    return result_func


def extract_first_state_field_or_any_group_prefixed_field(
    _result_prefix_len: int,
    /,
    name: str,
    *,
    then: Callable[[str], Any] = identity,
    else_default=None,
) -> Callable[[str], Any]:
    def result_func(response: str):
        response_items = iter(response[_result_prefix_len:].split(","))

        try:
            # STATE ON/OFF
            state_key, state_value = next(response_items), next(response_items)
        except StopIteration:
            return else_default

        if name == state_key:
            return then(state_value)

        param_group, param_name = name.split(",")

        # <AM|FM|PM|PWM... etc> / <CARR>
        for group in response_items:
            if group == param_group:
                break
        else:
            return else_default

        return find_first_by_key(
            param_name,
            group_by_two(response_items),
            transform_found=then,
            not_found=else_default,
        )

    return result_func


# ---------------------------------------------------------------


def extract_regular_field(
    _result_prefix_len: int,
    /,
    name: str,
    *,
    then: Callable[[str], Any] = identity,
    else_default=None,
) -> Callable[[str], Any]:
    def result_func(response: str):
        return find_first_by_key(
            name,
            group_by_two(response[_result_prefix_len:].split(",")),
            transform_found=then,
            not_found=else_default,
        )

    return result_func


# ---------------------------------------------------------------


def extract_regular_field_before_group_or_group_prefixed_field(
    _group: str,
    _result_prefix_len: int,
    /,
    name: str,
    *,
    then: Callable[[str], Any] = identity,
    else_default=None,
) -> Callable[[str], Any]:

    if not name.startswith(_group + ","):

        def result_func(response: str):
            items = takewhile(
                lambda str: str != _group,
                iter(response[_result_prefix_len:].split(",")),
            )

            return find_first_by_key(
                name,
                group_by_two(items),
                transform_found=then,
                not_found=else_default,
            )

    else:
        name = name[len(_group) + 1 :]

        def result_func(response: str):
            items = (iter(response[_result_prefix_len:].split(",")),)

            for item in items:
                if item == _group:
                    break
            else:
                return else_default

            return find_first_by_key(
                name,
                group_by_two(items),
                transform_found=then,
                not_found=else_default,
            )

    return result_func
