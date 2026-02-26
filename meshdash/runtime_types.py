from typing import Callable, Optional

from .revision import RevisionInfo
from .state_payload_contracts import DashboardStatePayload

MeshTargetLabelFn = Callable[[object], str]
OpenMeshInterfaceFn = Callable[[object], object]
SubscribeFn = Callable[[object, str], None]
SeedTrackerFn = Callable[[object, object], None]
RevisionInfoFn = Callable[[], RevisionInfo]

StatePayload = DashboardStatePayload | dict[str, object]

BuildStateFn = Callable[..., StatePayload]
BuildNodeHistoryLoaderFn = Callable[..., Callable[..., dict]]
BuildOnlineActivityLoaderFn = Callable[..., Callable[..., dict]]
BuildSendChatLoaderFn = Callable[..., Callable[..., dict]]
BuildStateSnapshotLoaderFn = Callable[..., Callable[[], dict]]

SendChatMessageFn = Callable[..., dict]
SendReactionPacketFn = Callable[..., object]
RawGetLocalNodeIdFn = Callable[..., str]
GetLocalNodeIdFn = Callable[[object], str]
LocalNodeIdFn = Callable[[], str]
RecordLocalChatFn = Callable[..., None]

NormalizeSingleEmojiFn = Callable[[object], tuple[Optional[str], Optional[int]]]
ToIntFn = Callable[[object], Optional[int]]
UtcNowFn = Callable[[], str]
NowUnixFn = Callable[[], float]
GetTimeoutSecondsFn = Callable[[], int]
ParseUtcTextToUnixFn = Callable[[object], Optional[float]]

RenderHtmlFn = Callable[..., str]
MakeHttpHandlerFn = Callable[..., object]
ThreadingHttpServerCls = Callable[[tuple[str, int], object], object]
GuessLanIpv4Fn = Callable[[], Optional[str]]

StateFn = Callable[[], StatePayload]
NodeHistoryFn = Callable[..., dict]
OnlineActivityFn = Callable[..., dict]
SendChatFn = Callable[..., dict]

TrackerPacket = dict[str, object]
TrackerParsedPacket = dict[str, object]
TrackerEdgeMap = dict[object, dict[str, object]]
DirectEdgeKey = Optional[tuple[str, str]]

ExtractDeliveryUpdateFn = Callable[..., object]
SetDeliveryStateFn = Callable[..., None]
ApplyTrackerObservationFn = Callable[..., DirectEdgeKey]
ApplyRoutingDeliveryUpdateFn = Callable[..., object]
RecordDirectEdgeObservationFn = Callable[..., object]

BuildPacketSummaryFn = Callable[..., TrackerPacket]
BuildChatEntryFromPacketFn = Callable[..., Optional[TrackerPacket]]
BuildTrackerPacketArtifactsFn = Callable[..., tuple[TrackerPacket, Optional[TrackerPacket]]]
ApplyTrackerStorageUpdatesFn = Callable[..., None]
ParseTrackerPacketFn = Callable[..., TrackerParsedPacket]
ProcessParsedTrackerPacketFn = Callable[..., None]
RecordTrackerPacketUnlockedFn = Callable[..., None]
RecordTrackerPacketUnlockedWithDependenciesFn = Callable[..., None]
RecordTrackerReceiveUnlockedFn = Callable[..., None]
ResolveTrackerNodeIdFromNumFn = Callable[..., Optional[str]]

GetNodeIdFromNumFn = Callable[[object, object], Optional[str]]
CalculateHopsFn = Callable[[object, object], Optional[int]]
ExtractPacketPositionFn = Callable[[TrackerPacket], Optional[TrackerPacket]]
ExtractPacketBatteryLevelFn = Callable[[TrackerPacket], Optional[int]]
ExtractReplyIdFn = Callable[[object], Optional[int]]
ExtractEmojiCodepointFn = Callable[[object], Optional[int]]
EmojiFromCodepointFn = Callable[[Optional[int]], Optional[str]]
FormatEpochFn = Callable[[object], str]
ToJsonableFn = Callable[[object], object]
