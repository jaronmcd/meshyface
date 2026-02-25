from typing import Any, Callable, Dict, Optional, Tuple

from .revision import RevisionInfo

MeshTargetLabelFn = Callable[[Any], str]
OpenMeshInterfaceFn = Callable[[Any], Any]
SubscribeFn = Callable[[Any, str], None]
SeedTrackerFn = Callable[[Any, Any], None]
RevisionInfoFn = Callable[[], RevisionInfo]

BuildStateFn = Callable[..., dict]
BuildNodeHistoryLoaderFn = Callable[..., Callable[..., dict]]
BuildOnlineActivityLoaderFn = Callable[..., Callable[..., dict]]
BuildSendChatLoaderFn = Callable[..., Callable[..., dict]]
BuildStateSnapshotLoaderFn = Callable[..., Callable[[], dict]]

SendChatMessageFn = Callable[..., dict]
SendReactionPacketFn = Callable[..., Any]
GetLocalNodeIdFn = Callable[[Any], str]

NormalizeSingleEmojiFn = Callable[[Any], tuple[Optional[str], Optional[int]]]
ToIntFn = Callable[[Any], Optional[int]]
UtcNowFn = Callable[[], str]

RenderHtmlFn = Callable[..., str]
MakeHttpHandlerFn = Callable[..., Any]
GuessLanIpv4Fn = Callable[[], Optional[str]]

StateFn = Callable[[], dict]
NodeHistoryFn = Callable[..., dict]
OnlineActivityFn = Callable[..., dict]
SendChatFn = Callable[..., dict]

TrackerPacket = Dict[str, Any]
TrackerParsedPacket = Dict[str, Any]
TrackerEdgeMap = Dict[Any, Dict[str, Any]]
DirectEdgeKey = Optional[Tuple[str, str]]

ExtractDeliveryUpdateFn = Callable[..., Any]
SetDeliveryStateFn = Callable[..., None]
ApplyTrackerObservationFn = Callable[..., DirectEdgeKey]
ApplyRoutingDeliveryUpdateFn = Callable[..., Any]
RecordDirectEdgeObservationFn = Callable[..., Any]

BuildPacketSummaryFn = Callable[..., TrackerPacket]
BuildChatEntryFromPacketFn = Callable[..., Optional[TrackerPacket]]
BuildTrackerPacketArtifactsFn = Callable[..., tuple[TrackerPacket, Optional[TrackerPacket]]]
ApplyTrackerStorageUpdatesFn = Callable[..., None]
ParseTrackerPacketFn = Callable[..., TrackerParsedPacket]
ProcessParsedTrackerPacketFn = Callable[..., None]
RecordTrackerPacketUnlockedFn = Callable[..., None]
RecordTrackerPacketUnlockedWithDependenciesFn = Callable[..., None]

GetNodeIdFromNumFn = Callable[[Any, Any], Optional[str]]
CalculateHopsFn = Callable[[Any, Any], Optional[int]]
ExtractPacketPositionFn = Callable[[TrackerPacket], Optional[TrackerPacket]]
ExtractPacketBatteryLevelFn = Callable[[TrackerPacket], Optional[int]]
ExtractReplyIdFn = Callable[[Any], Optional[int]]
ExtractEmojiCodepointFn = Callable[[Any], Optional[int]]
EmojiFromCodepointFn = Callable[[Optional[int]], Optional[str]]
FormatEpochFn = Callable[[Any], str]
ToJsonableFn = Callable[[Any], Any]
