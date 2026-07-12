#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from playwright.async_api import Page, async_playwright


LOCAL_URL = "http://127.0.0.1:8877/"
REMOTE_URL = "http://192.168.1.67:8877/"


async def _snapshot(page: Page) -> dict[str, object]:
    return await page.evaluate(
        """() => {
          const frameState = collectFileTransferFrames(latestState, { respectActiveChannel: false });
          const rows = buildFileTransferRows(latestState).map((row) => ({
            key: row.key,
            transferId: row.transferId,
            direction: row.directionClass,
            peerId: row.peerId,
            fileName: row.fileName,
            progress: row.progressLabel,
            percent: row.progressPercent,
            canDownload: !!row.canDownload,
            delivered: !!row.delivered,
            channelIndex: row.channelIndex,
          }));
          return {
            localNodeId: normalizeNodeId(resolveLocalNodeId(latestState) || ""),
            sessions: Array.from(fileTransferOutgoingByToken.entries()).map(([token, session]) => ({
              token,
              transferId: session.transferId,
              senderId: session.senderId,
              destination: session.destination,
              channelIndex: session.channelIndex,
              fileName: session.fileName,
              waitingForAccept: !!session.waitingForAccept,
              acceptedAtMs: session.acceptedAtMs,
              sentChunks: session.sentChunks,
              ackedChunks: session.ackedChunks,
              totalChunks: session.totalChunks,
              delivered: !!session.delivered,
              failed: !!session.failed,
              pausedForPeerOffline: !!session.pausedForPeerOffline,
              ackWatermarkUnix: session.ackWatermarkUnix,
            })),
            acks: Array.from(frameState.ackByTransferKey.entries()).map(([key, ack]) => ({
              key,
              transferId: ack.transferId,
              originalSenderId: ack.originalSenderId,
              originalReceiverId: ack.originalReceiverId,
              channelIndex: ack.channelIndex,
              receivedCount: ack.receivedCount,
              totalChunks: ack.totalChunks,
              latestUnix: ack.latestUnix,
            })),
            rows,
            console: String(document.getElementById("files-console-log")?.textContent || ""),
          };
        }"""
    )


async def _prepare(page: Page, url: str) -> str:
    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    await page.wait_for_selector("#files-input", state="attached", timeout=30_000)
    await page.wait_for_function(
        "() => typeof latestState === 'object' && !!normalizeNodeId(resolveLocalNodeId(latestState) || '')",
        timeout=30_000,
    )
    await page.evaluate("applyLayoutView('files', false)")
    await page.wait_for_selector("#files-input", state="visible", timeout=10_000)
    return await page.evaluate("normalizeNodeId(resolveLocalNodeId(latestState) || '')")


async def _cancel_incomplete_inbound_transfers(page: Page) -> list[str]:
    canceled = await page.evaluate(
        """() => {
          const canceled = [];
          for (const row of buildFileTransferRows(latestState)) {
            if (!row || row.directionClass !== "inbound" || row.delivered || row.canDownload) continue;
            const key = String(row.key || "").trim();
            if (!key) continue;
            setFileTransferInboundDecisionByKey(key, "declined", {
              transferId: row.transferId,
              senderId: row.fromId,
              receiverId: row.toId,
              fileName: row.fileName,
            });
            setFileTransferInboundFlowStateByKey(key, "canceled-by-receiver", {
              transferId: row.transferId,
              senderId: row.fromId,
              receiverId: row.toId,
            });
            canceled.push(key);
          }
          if (canceled.length) scheduleFileTransferMaintenance(latestState);
          return canceled;
        }"""
    )
    return [str(value) for value in canceled] if isinstance(canceled, list) else []


async def run_transfer(
    *,
    sender_url: str,
    receiver_url: str,
    fixture: Path,
    timeout_seconds: int,
    output_dir: Path,
) -> dict[str, object]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(accept_downloads=True)
        sender = await context.new_page()
        receiver = await context.new_page()
        sender_id, receiver_id = await asyncio.gather(
            _prepare(sender, sender_url),
            _prepare(receiver, receiver_url),
        )
        if sender_id == receiver_id:
            raise RuntimeError(f"sender and receiver resolved to the same node: {sender_id}")

        canceled = await _cancel_incomplete_inbound_transfers(receiver)
        if canceled:
            print(json.dumps({"canceled_stale_inbound": canceled}), flush=True)
            await asyncio.sleep(6)
        receiver_toggle = receiver.locator("#files-auto-accept-toggle")
        if not await receiver_toggle.is_checked():
            await receiver_toggle.check()
        await sender.locator("#files-destination-input").fill(receiver_id)
        await sender.locator("#files-input").set_input_files(str(fixture))
        await sender.locator("#files-send-btn").click()

        started = time.monotonic()
        last_signature = ""
        sender_snapshot: dict[str, object] = {}
        receiver_snapshot: dict[str, object] = {}
        completed_row: dict[str, object] | None = None
        sender_delivered = False
        while (time.monotonic() - started) < timeout_seconds:
            await asyncio.sleep(2)
            sender_snapshot, receiver_snapshot = await asyncio.gather(
                _snapshot(sender),
                _snapshot(receiver),
            )
            signature = json.dumps(
                {
                    "sender_sessions": sender_snapshot.get("sessions"),
                    "sender_acks": sender_snapshot.get("acks"),
                    "receiver_rows": receiver_snapshot.get("rows"),
                },
                sort_keys=True,
            )
            if signature != last_signature:
                print(signature, flush=True)
                last_signature = signature
            rows = receiver_snapshot.get("rows")
            if isinstance(rows, list):
                completed_row = next(
                    (
                        row
                        for row in rows
                        if isinstance(row, dict)
                        and row.get("fileName") == fixture.name
                        and bool(row.get("canDownload"))
                    ),
                    None,
                )
            sessions = sender_snapshot.get("sessions")
            sender_delivered = bool(
                isinstance(sessions, list)
                and any(
                    isinstance(session, dict)
                    and session.get("fileName") == fixture.name
                    and bool(session.get("delivered"))
                    for session in sessions
                )
            )
            if completed_row is not None and sender_delivered:
                break

        result: dict[str, object] = {
            "sender_url": sender_url,
            "receiver_url": receiver_url,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "fixture": str(fixture),
            "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "sender": sender_snapshot,
            "receiver": receiver_snapshot,
            "completed": completed_row is not None,
            "sender_delivered": sender_delivered,
        }
        if completed_row is not None:
            transfer_key = str(completed_row.get("key") or "")
            download_button = receiver.locator(
                f'[data-action="download"][data-transfer-key="{transfer_key}"]'
            )
            if await download_button.count() == 1:
                async with receiver.expect_download(timeout=15_000) as download_info:
                    await download_button.click()
                download = await download_info.value
                output_dir.mkdir(parents=True, exist_ok=True)
                download_path = output_dir / f"received-{sender_id[1:]}-{fixture.name}"
                await download.save_as(str(download_path))
                result["download_path"] = str(download_path)
                result["download_sha256"] = hashlib.sha256(download_path.read_bytes()).hexdigest()
                result["hash_match"] = result["download_sha256"] == result["fixture_sha256"]
        await browser.close()
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--direction", choices=("remote-to-local", "local-to-remote"), required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/meshyface-file-e2e"))
    args = parser.parse_args()
    if not args.fixture.is_file():
        parser.error(f"fixture not found: {args.fixture}")
    sender_url, receiver_url = (
        (REMOTE_URL, LOCAL_URL)
        if args.direction == "remote-to-local"
        else (LOCAL_URL, REMOTE_URL)
    )
    result = asyncio.run(
        run_transfer(
            sender_url=sender_url,
            receiver_url=receiver_url,
            fixture=args.fixture.resolve(),
            timeout_seconds=max(10, args.timeout),
            output_dir=args.output_dir,
        )
    )
    print(json.dumps(result, indent=2), flush=True)
    return (
        0
        if result.get("completed")
        and result.get("sender_delivered")
        and result.get("hash_match")
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
