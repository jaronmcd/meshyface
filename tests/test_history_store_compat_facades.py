from meshdash import history_store_chat as history_store_chat_module
from meshdash import history_store_connections as history_store_connections_module
from meshdash import history_store_nodes as history_store_nodes_module
from meshdash import history_store_packets as history_store_packets_module
from meshdash import history_store_reads as history_store_reads_module
from meshdash import history_store_summary as history_store_summary_module
from meshdash import history_store_writes as history_store_writes_module


def test_history_store_reads_facade_reexports_domain_read_functions():
    assert history_store_reads_module.load_recent_packets is history_store_packets_module.load_recent_packets
    assert history_store_reads_module.load_recent_chat is history_store_chat_module.load_recent_chat
    assert history_store_reads_module.load_connections is history_store_connections_module.load_connections
    assert history_store_reads_module.load_node_history is history_store_nodes_module.load_node_history
    assert history_store_reads_module.load_online_activity is history_store_nodes_module.load_online_activity
    assert history_store_reads_module.load_summary_metrics is history_store_summary_module.load_summary_metrics
    assert history_store_reads_module.load_node_saved_counts is history_store_nodes_module.load_node_saved_counts
    assert history_store_reads_module.load_node_capabilities is history_store_nodes_module.load_node_capabilities


def test_history_store_writes_facade_reexports_domain_write_functions():
    assert history_store_writes_module.save_packet is history_store_packets_module.save_packet
    assert history_store_writes_module.save_chat is history_store_chat_module.save_chat
    assert (
        history_store_writes_module.save_connection_event
        is history_store_connections_module.save_connection_event
    )
    assert history_store_writes_module.save_summary_metrics is history_store_summary_module.save_summary_metrics
