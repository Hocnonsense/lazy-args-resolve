import inspect

import pytest

from lazy_args.wrapper import (
    call_with_context,
    extract_deps,
    resolve_lambda,
    resolve_lazy_parameters,
)


class TestExtractDeps:
    def test_global_dependency(self):
        assert extract_deps(lambda: b + 1) == {"b"}

    def test_multiple_globals(self):
        assert extract_deps(lambda: a + b * c) == {"a", "b", "c"}

    def test_closure_dependency(self):
        def make():
            x = 1
            return lambda: x + 1

        assert extract_deps(make()) == {"x"}

    def test_builtins_are_not_misreported_as_strings(self):
        assert extract_deps(lambda: len("x") + 1) == {"len"}


class TestCallWithContext:
    def test_no_deps_passthrough(self):
        assert call_with_context(lambda: 42, {}) == 42
        assert call_with_context(lambda: 1 + 1, {"unused": 99}) == 2

    def test_global_override(self):
        assert call_with_context(lambda: a * 2, {"a": 21}) == 42

    def test_closure_injection(self):
        def make():
            hidden = 1
            return lambda: hidden + 1

        assert call_with_context(make(), {"hidden": 41}) == 42
        assert call_with_context(make(), {"hidden1": 41}) == 2


class TestResolveLazyParameters:
    def bind(self, func, *args, **kwargs):
        sig = inspect.signature(func)
        return sig.bind(*args, **kwargs)

    def test_plain_arguments(self):
        def f(a, b):
            pass

        bound = self.bind(f, 1, 2)
        resolved = resolve_lazy_parameters(bound, inspect.signature(f).parameters)
        assert resolved == {"a": 1, "b": 2}

    def test_single_lazy(self):
        def f(a, b=lambda: a + 1):
            return a + b()

        sig = inspect.signature(f)
        bound = sig.bind(10)
        bound.apply_defaults()
        resolved = resolve_lazy_parameters(bound, sig.parameters)
        assert resolved["a"] == 10
        assert resolved["b"] == 11

    def test_escape_lazy(self):
        a = 1

        def f(a, b=lambda: lambda: a + 3):
            return a, b()

        sig = inspect.signature(f)
        bound = sig.bind(lambda: lambda: 1)
        bound.apply_defaults()
        resolved = resolve_lazy_parameters(bound, sig.parameters)
        assert resolved["a"]() == 1
        assert resolved["b"]() == 4

    def test_dependency_chain(self):
        def f(a, b=lambda: a + 1, c=lambda: b * 2):
            return a + b() * c()

        sig = inspect.signature(f)
        bound = sig.bind(a=1)
        bound.apply_defaults()
        resolved = resolve_lazy_parameters(bound, sig.parameters)
        assert resolved == {"a": 1, "b": 2, "c": 4}

    def test_cyclic_dependency_raises(self):
        def f(a=lambda: b, b=lambda: a):
            return a + b()

        sig = inspect.signature(f)
        bound = sig.bind()
        bound.apply_defaults()
        with pytest.raises(ValueError, match="Circular"):
            resolve_lazy_parameters(bound, sig.parameters)
        sig = inspect.signature(f)
        bound = sig.bind(lambda: a)
        bound.apply_defaults()
        with pytest.raises(ValueError, match="Circular"):
            resolve_lazy_parameters(bound, sig.parameters)

    def test_lambda_referencing_non_param_global(self):
        BASE = 1

        def f(a=lambda: BASE + 1):
            return a

        sig = inspect.signature(f)
        bound = sig.bind()
        bound.apply_defaults()
        resolved = resolve_lazy_parameters(bound, sig.parameters)
        assert resolved["a"] == 2


class TestLazyEvaluate:
    def test_deep_chain(self):
        @resolve_lambda
        def f(a=lambda: b + 1, b=lambda: c * 2, c=1):
            return a() + b() + c

        assert f() == 6
        assert f(c=5) == 26

    def test_plain_positional(self):
        @resolve_lambda
        def f(a, b=lambda: a * 10):
            return a + b()

        assert f(3) == 33

    def test_no_lambdas_is_transparent(self):
        @resolve_lambda
        def f(a, b=2):
            return a + b

        assert f(1) == 3

    def test_mixed_resolution_order(self):
        calls = []

        @resolve_lambda
        def f(
            a=lambda: calls.append("a") or 1,
            b=lambda: calls.append("b") or a + 1,
        ):
            return a() + b()

        assert f() == 3
        assert calls == ["a", "b"]
