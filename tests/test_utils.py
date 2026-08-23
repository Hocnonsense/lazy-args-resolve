from lazy_args.utils import find_cycle, report_deps_error


class TestFindCycle:
    def test_no_cycle(self):
        pending = {"a": {"deps": {"b"}}, "b": {"deps": set()}}
        assert find_cycle(pending) is None

    def test_simple_cycle(self):
        pending = {"a": {"deps": {"b"}}, "b": {"deps": {"a"}}}
        cycle = find_cycle(pending)
        assert cycle is not None
        assert cycle[0] == cycle[-1]

    def test_self_cycle(self):
        pending = {"a": {"deps": {"a"}}}
        assert find_cycle(pending) == ["a", "a"]

    def test_deps_outside_pending_are_ignored(self):
        pending = {"a": {"deps": {"ghost"}}}
        assert find_cycle(pending) is None


class TestReportDepsError:
    def test_cycle_message(self):
        pending = {"a": {"deps": {"b"}}, "b": {"deps": {"a"}}}
        assert "Circular" in report_deps_error(pending)

    def test_fallback_lists_pending(self):
        pending = {"a": {"deps": {"b"}}}
        msg = report_deps_error(pending)
        assert "a depends on: b" in msg
