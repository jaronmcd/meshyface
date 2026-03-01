from .http_api_get import build_get_route_dependencies, make_get_dispatch
from .http_api_post import build_post_route_dependencies, make_post_dispatch
from .http_handler import build_dashboard_handler_class
from .helpers import to_int
from .http_route_contracts import (
    GetThemeSettingsFn,
    NodeHistoryFn,
    OnlineActivityFn,
    SummaryMetricsHistoryFn,
    SendChatFn,
    SetThemePresetFn,
    StateFn,
    ToIntFn,
)


def make_http_handler(
    html_text: str,
    state_fn: StateFn,
    node_history_fn: NodeHistoryFn | None = None,
    online_activity_fn: OnlineActivityFn | None = None,
    summary_metrics_fn: SummaryMetricsHistoryFn | None = None,
    send_chat_fn: SendChatFn | None = None,
    get_theme_settings_fn: GetThemeSettingsFn | None = None,
    set_theme_preset_fn: SetThemePresetFn | None = None,
    default_node_history_hours: int = 72,
    to_int_fn: ToIntFn = to_int,
):
    apply_radio_settings_fn = getattr(state_fn, "apply_radio_settings_fn", None)
    get_deps = build_get_route_dependencies(
        html_text=html_text,
        state_fn=state_fn,
        node_history_fn=node_history_fn,
        online_activity_fn=online_activity_fn,
        summary_metrics_fn=summary_metrics_fn,
        get_theme_settings_fn=get_theme_settings_fn,
        default_node_history_hours=default_node_history_hours,
        to_int_fn=to_int_fn,
    )
    post_deps = build_post_route_dependencies(
        send_chat_fn=send_chat_fn,
        set_theme_preset_fn=set_theme_preset_fn,
        apply_radio_settings_fn=apply_radio_settings_fn,
        to_int_fn=to_int_fn,
    )

    return build_dashboard_handler_class(
        dispatch_get_fn=make_get_dispatch(deps=get_deps),
        dispatch_post_fn=make_post_dispatch(deps=post_deps),
    )
