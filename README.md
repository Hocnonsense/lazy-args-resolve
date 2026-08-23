lazy-args-resolve
===

Lazy argument evaluation for Python: the `@resolve_lambda` decorator defers evaluation of zero-argument lambda defaults until call time, resolving them automatically by their dependency relationships.

```python
from lazy_args import resolve_lambda


@resolve_lambda
def f(a=lambda: b + 1, b=lambda: a * 2):
    return a() + b()


f(10)      # 30   -> b depends on a, a=10 resolved
f(b=1)     # 3    -> a depends on b, b=1 resolved
```

## Feature
- `resolve_lambda` acts as a decorator: it recognizes **zero-argument lambdas** in parameter defaults or passed as arguments, and resolves them iteratively by dependency ordering.
- If resolution fails, e.g. on circular dependencies, a `ValueError` is raised.
- Inside the function body, parameters whose defaults are **zero-argument lambdas** remain callable (`a()`), preserving the original lambda semantics. To keep a lambda from being resolved, use a named function or `lambda: lambda: ...`.


## How it works
- `extract_deps` inspects the bytecode (`dis`) of a lambda to collect its references to the enclosing scope as a dependency set.
- Dependency extraction relies on bytecode instructions (`LOAD_GLOBAL` / `LOAD_DEREF` / `LOAD_NAME`); indirect references inside the lambda body (e.g. `f` in `lambda: f(x)`) are also collected and may be misidentified as dependencies if they collide with parameter names.

## Testing
```bash
pixi run test   # pytest, includes --doctest-modules automatically
```
