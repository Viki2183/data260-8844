"""HW8 consumer-death readiness and event helpers.

The live harness is intentionally not run by this module import.  Kafka
readiness is checked through the broker's consumer-group metadata before a
future experiment publishes its single task.
"""

from __future__ import annotations

import asyncio
import argparse
import json
import os
import shutil
import struct
import subprocess
import time
from collections.abc import Mapping
from typing import Any

from hw08_kafka_config import KAFKA_BOOTSTRAP_SERVERS, TASKS_TOPIC, WRITER_CONSUMER_GROUP

CRASH_POINT = "after_receipt_before_output_and_commit"
REQUIRED_GROUP_STATE = "STABLE"
GROUP_TUPLE_FIELDS = (
    "error_code",
    "group",
    "state",
    "protocol_type",
    "protocol",
    "members",
    "authorized_operations",
)
GROUP_TUPLE_FIELDS_V2 = GROUP_TUPLE_FIELDS[:6]
MEMBER_TUPLE_FIELDS = (
    "member_id",
    "client_id",
    "client_host",
    "member_metadata",
    "member_assignment",
)


def parse_harness_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse explicit arguments without contacting Kafka or publishing data."""
    parser = argparse.ArgumentParser(description="HW8 consumer-death harness")
    parser.add_argument("--group-id", default=WRITER_CONSUMER_GROUP)
    parser.add_argument("--topic", default=TASKS_TOPIC)
    parser.add_argument("--bootstrap-servers", default=KAFKA_BOOTSTRAP_SERVERS)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--validate-args", action="store_true")
    args = parser.parse_args(argv)
    if args.group_id != WRITER_CONSUMER_GROUP:
        parser.error(f"group id must be {WRITER_CONSUMER_GROUP!r}")
    if args.topic != TASKS_TOPIC:
        parser.error(f"topic must be {TASKS_TOPIC!r}")
    if args.live and args.validate_args:
        parser.error("--live and --validate-args are mutually exclusive")
    return args


def _stable_state(state: Any) -> bool:
    return _text(state).upper().endswith(REQUIRED_GROUP_STATE)


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _field(value: Any, *names: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
    else:
        for name in names:
            if hasattr(value, name):
                return getattr(value, name)
        getter = getattr(value, "get_item", None)
        if getter is not None:
            for name in names:
                try:
                    return getter(name)
                except KeyError:
                    continue
    return default


def _safe_shape(value: Any) -> dict[str, Any]:
    """Return only structural names, never values, for bounded diagnostics."""
    if isinstance(value, Mapping):
        return {"type": type(value).__name__, "mapping_keys": sorted(map(str, value.keys()))}
    attributes = sorted(
        name for name in dir(value) if not name.startswith("_")
    )
    return {"type": type(value).__name__, "attributes": attributes[:40]}


def _decode_assignment_bytes(raw: bytes) -> dict[str, Any]:
    """Decode Kafka ConsumerProtocolMemberAssignment bytes without broker access."""
    cursor = 0

    def take(fmt: str) -> tuple[Any, ...]:
        nonlocal cursor
        size = struct.calcsize(fmt)
        if cursor + size > len(raw):
            raise ValueError("truncated member assignment")
        values = struct.unpack_from(fmt, raw, cursor)
        cursor += size
        return values

    (version,) = take(">h")
    (topic_count,) = take(">i")
    if topic_count < 0 or topic_count > 1000:
        raise ValueError("invalid assignment topic count")
    assignments: list[tuple[str, list[int]]] = []
    for _ in range(topic_count):
        (length,) = take(">h")
        if length < 0 or cursor + length > len(raw):
            raise ValueError("invalid assignment topic length")
        topic = raw[cursor : cursor + length].decode("utf-8")
        cursor += length
        (partition_count,) = take(">i")
        if partition_count < 0 or partition_count > 10000:
            raise ValueError("invalid assignment partition count")
        partitions = [take(">i")[0] for _ in range(partition_count)]
        assignments.append((topic, partitions))
    (user_data_length,) = take(">i")
    if user_data_length < 0 or cursor + user_data_length > len(raw):
        raise ValueError("invalid assignment user-data length")
    return {"version": version, "assignment": assignments}


def _normalize_member_entry(member: Any) -> Any:
    if not isinstance(member, tuple):
        return member
    if len(member) != len(MEMBER_TUPLE_FIELDS):
        raise ValueError(
            f"unsupported member tuple length {len(member)}; "
            f"expected {len(MEMBER_TUPLE_FIELDS)}"
        )
    return dict(zip(MEMBER_TUPLE_FIELDS, member))


def _normalize_group_entry(entry: Any) -> Any:
    if not isinstance(entry, tuple):
        return entry
    if len(entry) == len(GROUP_TUPLE_FIELDS_V2):
        fields = GROUP_TUPLE_FIELDS_V2
    elif len(entry) == len(GROUP_TUPLE_FIELDS):
        fields = GROUP_TUPLE_FIELDS
    else:
        raise ValueError(
            f"unsupported group tuple length {len(entry)}; expected "
            f"{len(GROUP_TUPLE_FIELDS_V2)} or {len(GROUP_TUPLE_FIELDS)}"
        )
    normalized = dict(zip(fields, entry))
    normalized["members"] = [
        _normalize_member_entry(member) for member in (normalized.get("members") or ())
    ]
    return normalized


def assignment_topics(description: Any) -> set[str]:
    """Extract assigned topic names from aiokafka objects or mappings."""
    topics: set[str] = set()
    members = _field(description, "members", default=()) or ()
    for member in members:
        assignment = _field(member, "assignment", "member_assignment", default=None)
        if assignment is None:
            continue
        if isinstance(assignment, bytes):
            try:
                assignment = _decode_assignment_bytes(assignment)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"member assignment decode failed: {exc}") from exc
        topic_partitions = _field(assignment, "topic_partitions", default=None)
        if topic_partitions is None:
            topic_partitions = _field(assignment, "assignment", default=None)
        if isinstance(topic_partitions, Mapping):
            for topic, partitions in topic_partitions.items():
                if isinstance(partitions, (list, tuple, set)):
                    topics.add(_text(topic))
                else:
                    topics.update(_assignment_topics(partitions))
        elif topic_partitions is not None:
            topics.update(_assignment_topics(topic_partitions))
        else:
            topics.update(_assignment_topics(assignment))
    return topics


def assignment_partitions_by_client(description: Any) -> dict[str, dict[str, list[int]]]:
    """Return decoded topic partitions grouped by safe client ID."""
    result: dict[str, dict[str, list[int]]] = {}
    for member in _field(description, "members", default=()) or ():
        client_id = _text(_field(member, "client_id", default="unknown"))
        assignment = _field(member, "assignment", "member_assignment", default=None)
        if isinstance(assignment, bytes):
            assignment = _decode_assignment_bytes(assignment)
        entries = _field(assignment, "topic_partitions", "assignment", default=()) or ()
        client_topics: dict[str, list[int]] = {}
        if isinstance(entries, Mapping):
            for topic, partitions in entries.items():
                client_topics[_text(topic)] = [int(partition) for partition in partitions]
        else:
            for entry in entries:
                topic_value = _field(entry, "topic", default=None)
                partitions_value = _field(entry, "partitions", default=None)
                if topic_value is not None and partitions_value is None:
                    partition_value = _field(entry, "partition", default=None)
                    if partition_value is not None:
                        partitions_value = [partition_value]
                    else:
                        partitions_value = []
                if topic_value is None and isinstance(entry, (tuple, list)) and len(entry) >= 2:
                    topic_value, partitions_value = entry[0], entry[1]
                if topic_value is None or partitions_value is None:
                    raise ValueError("ambiguous assignment entry")
                topic = _text(topic_value)
                partitions = partitions_value
                client_topics[topic] = [int(partition) for partition in partitions]
        result[client_id] = client_topics
    return result


def _assignment_topics(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        topics: set[str] = set()
        for key, nested in value.items():
            if isinstance(nested, (list, tuple, set)):
                topics.add(_text(key))
            else:
                topics.update(_assignment_topics(nested))
        return topics
    if isinstance(value, (list, tuple, set)):
        topics: set[str] = set()
        for item in value:
            topic = _field(item, "topic", "topic_name", default=None)
            if topic is not None:
                topics.add(_text(topic))
            elif isinstance(item, (list, tuple)) and item:
                topics.add(_text(item[0]))
            else:
                topics.update(_assignment_topics(item))
        return topics
    topic = _field(value, "topic", "topic_name", default=None)
    return {_text(topic)} if topic is not None else set()


def group_ready(
    description: Any,
    *,
    group_id: str = WRITER_CONSUMER_GROUP,
    topic: str = TASKS_TOPIC,
) -> bool:
    """Return true only for a stable group with a member assigned to topic."""
    actual_group_id = _field(description, "group_id", "group", default=None)
    members = _field(description, "members", default=()) or ()
    return (
        _text(actual_group_id) == group_id
        and _stable_state(_field(description, "state", "group_state", default=""))
        and len(members) > 0
        and topic in assignment_topics(description)
    )


def readiness_snapshot(description: Any, *, topic: str = TASKS_TOPIC) -> dict[str, Any]:
    """Create auditable readiness metadata without contacting Kafka."""
    topics = sorted(assignment_topics(description))
    return {
        "group_id": _text(_field(description, "group_id", "group", default="unknown")),
        "group_state": _text(_field(description, "state", "group_state", default="unknown")),
        "active_member_count": len(_field(description, "members", default=()) or ()),
        "assigned_topics": topics,
        "assigned_partitions_by_client": assignment_partitions_by_client(description),
        "required_topic": topic,
        "ready": group_ready(description, topic=topic),
    }


def normalize_group_description(response: Any, group_id: str) -> Any | None:
    """Select one group from raw aiokafka DescribeGroupsResponse wrappers."""
    candidates: list[Any] = []
    if isinstance(response, Mapping):
        direct = response.get(group_id)
        if direct is not None:
            return direct
        wrapped = response.get("groups")
        candidates.extend(wrapped if isinstance(wrapped, (list, tuple)) else response.values())
    elif isinstance(response, (list, tuple)):
        for item in response:
            wrapped = _field(item, "groups", default=None)
            if isinstance(wrapped, (list, tuple)):
                candidates.extend(wrapped)
            else:
                candidates.append(item)
    else:
        wrapped = _field(response, "groups", default=None)
        if isinstance(wrapped, (list, tuple)):
            candidates.extend(wrapped)
        else:
            candidates.append(response)

    for candidate in candidates:
        candidate = _normalize_group_entry(candidate)
        candidate_group_id = _field(candidate, "group_id", "group", default=None)
        if _text(candidate_group_id) == group_id:
            return candidate
    return None


def _group_entries(response: Any) -> list[Any]:
    """Explicitly unwrap list[DescribeGroupsResponse]."""
    entries: list[Any] = []
    outer = response if isinstance(response, (list, tuple)) else [response]
    for response_item in outer:
        groups = _field(response_item, "groups", default=None)
        if groups is None:
            continue
        if not isinstance(groups, (list, tuple)):
            raise TypeError("DescribeGroupsResponse.groups is not a list")
        entries.extend(groups)
    return entries


def response_diagnostic(response: Any, group_id: str, error: Exception | None = None) -> dict[str, Any]:
    """Build safe parser diagnostics without response values or payloads."""
    diagnostic: dict[str, Any] = {
        "requested_group_id": group_id,
        "raw_response_type": type(response).__name__,
        "response_shape": _safe_shape(response),
        "normalized_group_entries": [],
    }
    if isinstance(response, (list, tuple)):
        diagnostic["outer_length"] = len(response)
        diagnostic["outer_item_shapes"] = [_safe_shape(item) for item in response[:10]]
    try:
        entries = _group_entries(response)
        for entry in entries[:20]:
            entry = _normalize_group_entry(entry)
            members = _field(entry, "members", default=()) or ()
            diagnostic["normalized_group_entries"].append(
                {
                    "group_shape": _safe_shape(entry),
                    "group_id": _text(_field(entry, "group_id", "group", default="unknown")),
                    "state": _text(_field(entry, "state", "group_state", default="unknown")),
                    "member_count": len(members),
                    "assigned_topics": sorted(assignment_topics(entry)),
                }
            )
    except Exception as exc:  # pragma: no cover - exercised by malformed fixtures
        diagnostic["parser_exception_type"] = type(exc).__name__
        diagnostic["parser_exception_message"] = str(exc)
    if error is not None:
        diagnostic["exception_type"] = type(error).__name__
        diagnostic["exception_message"] = str(error)
    return diagnostic


def parse_cli_readiness(
    state_output: str,
    describe_output: str,
    *,
    group_id: str = WRITER_CONSUMER_GROUP,
    topic: str = TASKS_TOPIC,
) -> dict[str, Any] | None:
    """Parse Kafka CLI --state/--describe output; ambiguity is failure."""
    if (
        not state_output
        or group_id not in state_output
        or "STABLE" not in state_output.upper()
    ):
        return None
    assignments = []
    for line in describe_output.splitlines():
        fields = line.split()
        if len(fields) >= 9 and fields[0] == group_id and fields[1] == topic:
            consumer_id = fields[6]
            if consumer_id != "-":
                assignments.append(fields[2])
    if not assignments:
        return None
    return {
        "group_id": group_id,
        "group_state": "STABLE",
        "active_member_count": len(set(assignments)),
        "assigned_topics": [topic],
        "required_topic": topic,
        "ready": True,
        "readiness_method": "kafka_cli_fallback",
    }


def cli_readiness_fallback(
    *,
    bootstrap_servers: str,
    group_id: str,
    topic: str,
    timeout_seconds: float = 5.0,
) -> dict[str, Any] | None:
    """Use Kafka CLI only when available; never treats missing output as ready."""
    configured = os.getenv("KAFKA_GROUPS_CLI", "/opt/kafka/bin/kafka-consumer-groups.sh")
    executable = configured if os.path.exists(configured) else shutil.which(configured)
    if executable is None:
        return None
    commands = [
        [executable, "--bootstrap-server", bootstrap_servers, "--state", "--group", group_id],
        [
            executable,
            "--bootstrap-server",
            bootstrap_servers,
            "--describe",
            "--group",
            group_id,
        ],
    ]
    try:
        outputs = [
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            for command in commands
        ]
    except (OSError, subprocess.TimeoutExpired):
        return None
    if any(result.returncode != 0 for result in outputs):
        return None
    return parse_cli_readiness(
        outputs[0].stdout,
        outputs[1].stdout,
        group_id=group_id,
        topic=topic,
    )


async def wait_for_writer_group(
    *,
    bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
    group_id: str = WRITER_CONSUMER_GROUP,
    topic: str = TASKS_TOPIC,
    timeout_seconds: float = 30.0,
    poll_seconds: float = 0.5,
    admin_client: Any | None = None,
    fallback_probe: Any = cli_readiness_fallback,
) -> dict[str, Any]:
    """Wait for stable Writer assignment; does not publish or retry a request."""
    owns_admin = admin_client is None
    if owns_admin:
        try:
            from aiokafka.admin import AIOKafkaAdminClient
        except ImportError as exc:  # pragma: no cover - live environment only
            raise RuntimeError("aiokafka is required for live group readiness") from exc
        admin = AIOKafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            request_timeout_ms=5000,
            client_id="hw08-consumer-death-readiness",
        )
    else:
        admin = admin_client
    if owns_admin:
        await admin.start()
    deadline = time.monotonic() + timeout_seconds
    last_snapshot = {
        "bootstrap_servers": bootstrap_servers,
        "requested_group_id": group_id,
        "raw_response_type": "none",
        "group_id": group_id,
        "ready": False,
        "reason": "no response",
    }
    try:
        while time.monotonic() < deadline:
            descriptions = None
            try:
                descriptions = await admin.describe_consumer_groups([group_id])
                if not descriptions:
                    raise ValueError("empty aiokafka admin response")
                description = normalize_group_description(descriptions, group_id)
                if description is None:
                    raise ValueError("unsupported aiokafka response shape")
            except Exception as exc:
                last_snapshot = response_diagnostic(descriptions, group_id, exc)
                description = None
            if description is not None and group_ready(description, topic=topic):
                snapshot = readiness_snapshot(description, topic=topic)
                snapshot["readiness_method"] = "aiokafka"
                return snapshot
            fallback = fallback_probe(
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                topic=topic,
            )
            if fallback is not None:
                return fallback
            await asyncio.sleep(poll_seconds)
    finally:
        if owns_admin:
            await admin.close()
    raise TimeoutError(
        f"Writer group {group_id!r} was not ready for {topic!r}; "
        f"diagnostic={last_snapshot}"
    )


def death_event(
    event_type: str,
    *,
    correlation_id: str,
    topic: str,
    partition: int,
    offset: int,
    process: str,
    timestamp: str,
    committed: bool,
    crash_point: str | None = None,
    duplicate_side_effect_prevented: bool | None = None,
) -> dict[str, Any]:
    """Build one explicit event for later live evidence collection."""
    event = {
        "event_type": event_type,
        "correlation_id": correlation_id,
        "topic": topic,
        "partition": partition,
        "offset": offset,
        "process": process,
        "timestamp": timestamp,
        "committed": committed,
    }
    if crash_point is not None:
        event["crash_point"] = crash_point
    if duplicate_side_effect_prevented is not None:
        event["duplicate_side_effect_prevented"] = duplicate_side_effect_prevented
    return event


def expected_consumer_death_sequence() -> tuple[str, ...]:
    """Return the required event order for validation of a future run."""
    return (
        "message_received",
        "pre_commit_crash",
        "writer_terminated",
        "message_redelivered",
        "output_published",
        "offset_committed",
    )


async def run_live_crash(args: argparse.Namespace) -> None:  # pragma: no cover - live only
    """Wait for Writers, then publish exactly one task; never join their group."""
    readiness = await wait_for_writer_group(
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        topic=args.topic,
    )
    writer_partitions = readiness.get("assigned_partitions_by_client", {}).get("writer-1", {}).get(args.topic, [])
    if not writer_partitions:
        raise RuntimeError("readiness did not identify a partition assigned to writer-1")
    from hw08_kafka_runtime import build_producer
    from hw08_messages import serialize_message

    # aiokafka 0.12.0 does not expose a producer-level ``retries``
    # constructor argument.  This harness performs exactly one publish call:
    # no application retry loop and no producer resend are implemented.  Any
    # internal client behavior is therefore not represented as a configurable
    # application retry count; the experiment records application retries as 0.
    producer = await build_producer(bootstrap_servers=args.bootstrap_servers)
    await producer.start()
    try:
        correlation_id = "hw8-8844-consumer-death-001"
        message = {
            "message_type": "task_message",
            "correlation_id": correlation_id,
            "data": {"question": "Produce one deterministic draft after Kafka redelivery."},
            "attempt": 1,
            "timestamp": "2026-10-31T09:10:00Z",
            "metadata": {"operation": "WRITE_DRAFT", "producer_retries": 0},
        }
        metadata = await producer.send_and_wait(
            args.topic,
            serialize_message(message),
            partition=writer_partitions[0],
        )
        print(
            json.dumps(
                {
                    "event_type": "task_published",
                    "group_id": args.group_id,
                    "topic": args.topic,
                    "partition": metadata.partition,
                    "offset": metadata.offset,
                    "correlation_id": correlation_id,
                    "readiness_method": readiness.get("readiness_method"),
                    "producer_retries": 0,
                }
            ),
            flush=True,
        )
    finally:
        await producer.stop()


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI wrapper
    args = parse_harness_args(argv)
    if args.validate_args:
        print(
            json.dumps(
                {
                    "group_id": args.group_id,
                    "topic": args.topic,
                    "bootstrap_servers": args.bootstrap_servers,
                    "live": False,
                }
            )
        )
        return
    if not args.live:
        raise SystemExit("pass --validate-args for offline validation or --live for approved Kafka execution")
    asyncio.run(run_live_crash(args))


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    main()
