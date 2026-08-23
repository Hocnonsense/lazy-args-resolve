import dis
import inspect
import types
from typing import Any, Callable, Final, Mapping

_EXTERNAL_LOAD_OPS: Final = frozenset({"LOAD_GLOBAL", "LOAD_DEREF", "LOAD_NAME"})


def is_lazy_lambda(func: Callable[..., Any]) -> bool:
    """Only lambda with no params is allowed as a lazy evaluator.

    >>> is_lazy_lambda(lambda: x)
    True
    >>> is_lazy_lambda(lambda x: x)
    False
    >>> is_lazy_lambda(lambda x=1: x)
    False
    >>> is_lazy_lambda(lambda *args: args)
    False
    >>> is_lazy_lambda(lambda **kwargs: kwargs)
    False
    >>> def f(): return 1
    ...
    >>> is_lazy_lambda(f)
    False
    >>> is_lazy_lambda(lambda: f())
    True
    """
    return (
        inspect.isfunction(func)
        and func.__name__ == "<lambda>"
        and not inspect.signature(func).parameters
    )


def extract_deps(func: Callable[[], Any]) -> set[str]:
    """Extract the direct dependencies of a lambda on its enclosing scope."""
    return {
        instr.argval
        for instr in dis.get_instructions(func)
        if instr.opname in _EXTERNAL_LOAD_OPS and isinstance(instr.argval, str)
    }


def call_with_context(
    func: Callable[[], Any],
    resolved_deps: Mapping[str, Any],
) -> Any:
    """Execute a lambda with its dependencies resolved.

    A new function is built from the same code object with the resolved
    dependencies injected into its globals and/or closure, then called
    immediately.
    """
    if not resolved_deps:
        return func()

    code = func.__code__

    # ---- closure / free variables ----
    new_closure = func.__closure__
    if code.co_freevars:
        old_cells = func.__closure__ or ()
        new_closure = tuple(
            types.CellType(resolved_deps[name]) if name in resolved_deps else cell
            for name, cell in zip(code.co_freevars, old_cells)
        )

    # ---- global variables ----
    global_overrides = {
        name: value
        for name, value in resolved_deps.items()
        if name in code.co_names and name not in code.co_freevars
    }
    new_globals = (
        {**func.__globals__, **global_overrides}
        if global_overrides
        else func.__globals__
    )
    return types.FunctionType(
        code, new_globals, func.__name__, func.__defaults__, new_closure
    )()


def resolve_lazy_parameters(
    bound: inspect.BoundArguments, params: Mapping[str, inspect.Parameter]
) -> dict[str, Any]:
    """Resolve all lazy parameters using dependency ordering."""
    resolved: dict[str, Any] = {}
    pending: dict[str, dict[str, Any]] = {}

    for name in params:
        value = bound.arguments[name]

        if is_lazy_lambda(value):
            pending[name] = {
                "func": value,
                "deps": extract_deps(value) & params.keys(),
            }
        else:
            resolved[name] = value

    # Repeatedly resolve parameters whose dependencies are ready.
    while pending:
        noprogress = True

        for name, info in list(pending.items()):
            deps = info["deps"]

            if deps <= resolved.keys():
                dep_values = {dep: resolved[dep] for dep in deps}

                resolved[name] = call_with_context(
                    info["func"],
                    dep_values,
                )

                del pending[name]
                noprogress = False

        if noprogress:
            from .utils import report_deps_error

            raise ValueError(report_deps_error(pending))

    return resolved


def revert_lambda(resolved: dict[str, Any], kept_lambda: set[str]):
    """Wrap resolved values back into zero-argument callables.

    Parameters whose *defaults* are lazy lambdas stay callable inside the
    wrapped function body, no matter whether their value was supplied as a
    plain argument or resolved lazily.

    >>> d = {'a': 1, 'b': 2}
    >>> revert_lambda(d, {'a'})
    {'a': 1}
    >>> d['a']()
    1
    >>> d['b']
    2
    """
    d = {name: resolved[name] for name in kept_lambda & resolved.keys()}
    # Keep parameters that were originally lazy defaults callable.
    for name in d:
        resolved[name] = lambda _=name: d[_]
    return d


def resolve_lambda(func):
    """
    Enable late resolve of zero-argument lambda defaults.

    Example:

    >>> @resolve_lambda
    ... def f(a=lambda: b + 1, b=lambda: a * 2):
    ...     return a() + b()
    ...
    >>> f(10)
    30
    >>> f(b=1)
    3
    """
    sig = inspect.signature(func)

    kept_lambda = {
        name
        for name, param in sig.parameters.items()
        if param.default is not inspect.Parameter.empty
        and is_lazy_lambda(param.default)
    }

    def inner(*_0, **_1):
        bound = sig.bind(*_0, **_1)
        bound.apply_defaults()

        bound.arguments = resolve_lazy_parameters(bound, sig.parameters)
        revert_lambda(bound.arguments, kept_lambda)
        return func(*bound.args, **bound.kwargs)

    return inner
