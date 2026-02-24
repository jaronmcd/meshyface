from meshdash import tracker_runtime as facade
from meshdash import tracker_runtime_impl as impl


def test_tracker_runtime_facade_reexports_impl_symbols():
    assert facade.DashboardTracker is impl.DashboardTracker
    assert facade.seed_tracker_from_node_db is impl.seed_tracker_from_node_db
