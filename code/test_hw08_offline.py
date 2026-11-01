"""Offline unit tests for the DATA260 HW8 foundation."""

from __future__ import annotations

import asyncio
import struct
import unittest
from unittest.mock import patch
import uuid

from hw08_entity_store import EntityStore
from hw08_entity_validation import validate_vulnerability_report
from hw08_entity_worker import CREATE_OPERATION, GET_OPERATION, process_entity_message
from hw08_failure_handling import (
    POISON_FIXTURE_MARKER,
    classify_poison_message,
    consumer_death_actions,
    dead_letter_message,
    poison_attempt_records,
    should_commit_after_dead_letter,
    should_commit_after_success,
    should_retry,
)
from hw08_agent_pipeline import crash_once_before_commit, stage_event
from hw08_agent_pipeline import transform_stage
from hw08_consumer_death_harness import (
    CRASH_POINT,
    assignment_topics,
    death_event,
    expected_consumer_death_sequence,
    group_ready,
    parse_harness_args,
    parse_cli_readiness,
    readiness_snapshot,
    normalize_group_description,
    response_diagnostic,
    wait_for_writer_group,
)
from hw08_poison_harness import parse_harness_args as parse_poison_harness_args
from homework_demo import parse_args as parse_homework_demo_args
from hw08_agent_demo import parse_args as parse_agent_demo_args
from hw08_ordering_harness import parse_args as parse_ordering_args
from hw08_ordering_harness import require_exact_two_partitions
from hw08_ordering_harness import read_topic_partitions
from hw08_kafka_runtime import build_producer
from hw08_kafka_config import (
    DEAD_LETTER_TOPIC,
    TASKS_TOPIC,
    all_required_topics,
    topic_creation_commands,
    validate_topic_set,
)
from hw08_messages import (
    build_entity_request,
    deserialize_message,
    idempotency_key,
    serialize_message,
)
from hw08_ordering import generate_ordering_messages, record_processing, records_to_rows

VALID_DATA = {
    "packageName": "requests",
    "vulnerabilityId": "CVE-2026-0001",
    "submitterEmail": "student@example.com",
    "vulnerabilityDescription": "A sufficiently detailed vulnerability description.",
    "severity": "High",
    "affectedVersionsCount": 2,
    "termsAccepted": True,
}


class Hw08OfflineTests(unittest.TestCase):
    def request(self, operation: str, data: dict) -> dict:
        return build_entity_request(
            correlation_id="corr-8844-001",
            reply_to="s8844_entity_responses",
            operation=operation,
            data=data,
            timestamp="2026-10-29T00:00:00Z",
        )

    def test_valid_payload(self) -> None:
        self.assertEqual(validate_vulnerability_report(VALID_DATA), [])

    def test_invalid_payload_reports_failures(self) -> None:
        errors = validate_vulnerability_report(
            {"packageName": "", "severity": "Unknown", "termsAccepted": False}
        )
        self.assertIn("packageName must be non-empty text", errors)
        self.assertIn("severity must be Critical, High, Medium, or Low", errors)
        self.assertIn("termsAccepted must be true", errors)

    def test_envelope_has_required_fields_and_stable_key(self) -> None:
        message = self.request(CREATE_OPERATION, VALID_DATA)
        self.assertEqual(message["correlation_id"], "corr-8844-001")
        self.assertEqual(message["reply_to"], "s8844_entity_responses")
        self.assertEqual(message["data"], VALID_DATA)
        self.assertEqual(idempotency_key(message)[1], "corr-8844-001")

    def test_create_generates_uuid_and_preserves_correlation(self) -> None:
        store = EntityStore()
        fixed_uuid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        response = process_entity_message(
            self.request(CREATE_OPERATION, VALID_DATA),
            store,
            uuid_factory=lambda: fixed_uuid,
        )
        self.assertTrue(response["success"])
        self.assertEqual(response["correlation_id"], "corr-8844-001")
        self.assertEqual(response["entity_id"], str(fixed_uuid))
        self.assertEqual(len(store.entities), 1)

    def test_duplicate_create_reuses_original_result(self) -> None:
        store = EntityStore()
        message = self.request(CREATE_OPERATION, VALID_DATA)
        first = process_entity_message(message, store, uuid_factory=lambda: uuid.UUID(int=1))
        second = process_entity_message(message, store, uuid_factory=lambda: uuid.UUID(int=2))
        self.assertEqual(first["entity_id"], second["entity_id"])
        self.assertTrue(second["metadata"]["duplicate"])
        self.assertEqual(len(store.entities), 1)

    def test_get_round_trip_and_missing_entity(self) -> None:
        store = EntityStore()
        create = process_entity_message(
            self.request(CREATE_OPERATION, VALID_DATA),
            store,
            uuid_factory=lambda: uuid.UUID(int=3),
        )
        get_response = process_entity_message(
            self.request(GET_OPERATION, {"entity_id": create["entity_id"]}), store
        )
        self.assertTrue(get_response["success"])
        self.assertEqual(get_response["entity_id"], create["entity_id"])
        missing = process_entity_message(
            self.request(GET_OPERATION, {"entity_id": "missing"}), store
        )
        self.assertFalse(missing["success"])
        self.assertEqual(missing["correlation_id"], "corr-8844-001")

    def test_unknown_operation_and_invalid_data_preserve_correlation(self) -> None:
        unknown = process_entity_message(
            self.request("UNKNOWN_OPERATION", {}), EntityStore()
        )
        invalid = process_entity_message(
            self.request(CREATE_OPERATION, {"packageName": "requests"}), EntityStore()
        )
        self.assertEqual(unknown["correlation_id"], "corr-8844-001")
        self.assertEqual(unknown["error"], "Unknown operation")
        self.assertEqual(invalid["correlation_id"], "corr-8844-001")
        self.assertFalse(invalid["success"])

    def test_serialization_round_trip(self) -> None:
        message = self.request(CREATE_OPERATION, VALID_DATA)
        self.assertEqual(deserialize_message(serialize_message(message)), message)

    def test_exact_topics_and_creation_commands(self) -> None:
        self.assertEqual(len(all_required_topics()), 7)
        validate_topic_set(set(all_required_topics()))
        self.assertEqual(len(topic_creation_commands()), 7)
        task_command = next(
            command for command in topic_creation_commands() if TASKS_TOPIC in command
        )
        self.assertEqual(task_command[task_command.index("--partitions") + 1], "2")
        self.assertEqual(DEAD_LETTER_TOPIC, "s8844_dead_letter")

    def test_agent_transformations_preserve_correlation(self) -> None:
        inbox = {
            "message_type": "question",
            "correlation_id": "agent-1",
            "data": {"question": "Explain Kafka"},
            "attempt": 1,
            "timestamp": "offline",
            "metadata": {},
        }
        planned = transform_stage("planner", inbox)
        drafted = transform_stage("writer", planned)
        reviewed = transform_stage("reviewer", drafted)
        self.assertEqual(reviewed["correlation_id"], "agent-1")
        self.assertEqual(reviewed["data"]["status"], "approved")

    def test_failure_decisions_and_dead_letter(self) -> None:
        self.assertTrue(should_retry(1, max_attempts=3))
        self.assertFalse(should_retry(3, max_attempts=3))
        self.assertTrue(should_commit_after_success(processed=True, published=True, error=False))
        self.assertFalse(should_commit_after_success(processed=True, published=False, error=False))
        message = self.request(CREATE_OPERATION, VALID_DATA)
        dead = dead_letter_message(
            message,
            error_type="poison",
            source_topic=TASKS_TOPIC,
            source_partition=1,
            source_offset=9,
        )
        self.assertEqual(dead["metadata"]["dead_letter_topic"], DEAD_LETTER_TOPIC)
        self.assertEqual(dead["correlation_id"], message["correlation_id"])
        self.assertEqual(
            consumer_death_actions(committed_before_failure=False)[0], "restart_consumer"
        )

    def test_poison_detection_and_bounded_attempt_increment(self) -> None:
        message = {
            "message_type": "task_message",
            "correlation_id": "poison-8844",
            "data": {"invalid_writer_fixture": True},
            "attempt": 1,
            "timestamp": "offline",
            "metadata": {"fixture": POISON_FIXTURE_MARKER},
        }
        self.assertEqual(classify_poison_message(message), "intentional_poison_fixture")
        failures = poison_attempt_records(
            message,
            error_type="intentional_poison_fixture",
            max_attempts=3,
        )
        self.assertEqual([failure["attempt"] for failure in failures], [1, 2, 3])
        self.assertFalse(failures[-1]["retry_scheduled"])

    def test_dead_letter_preserves_source_and_correlation(self) -> None:
        message = {
            "message_type": "task_message",
            "correlation_id": "poison-8844",
            "data": {"invalid_writer_fixture": True},
            "attempt": 1,
            "timestamp": "offline",
            "metadata": {"fixture": POISON_FIXTURE_MARKER},
        }
        failures = poison_attempt_records(
            message,
            error_type="intentional_poison_fixture",
            max_attempts=3,
        )
        dead = dead_letter_message(
            message,
            error_type="intentional_poison_fixture",
            source_topic=TASKS_TOPIC,
            source_partition=0,
            source_offset=4,
            attempt=3,
            failure_metadata=failures,
        )
        self.assertEqual(dead["correlation_id"], message["correlation_id"])
        self.assertEqual(dead["metadata"]["source_topic"], TASKS_TOPIC)
        self.assertEqual(dead["metadata"]["source_offset"], 4)
        self.assertEqual(dead["metadata"]["attempts"], 3)
        self.assertEqual(dead["metadata"]["failed_attempts"], failures)
        self.assertEqual(dead["original_message"], message)

    def test_dead_letter_commit_requires_successful_publication(self) -> None:
        self.assertFalse(should_commit_after_dead_letter(published=False))
        self.assertTrue(should_commit_after_dead_letter(published=True))

    def test_poison_harness_arguments_and_no_resend_contract(self) -> None:
        args = parse_poison_harness_args(
            [
                "--validate-args",
                "--group-id",
                "s8844-writer",
                "--topic",
                "s8844_tasks",
                "--dead-letter-topic",
                "s8844_dead_letter",
                "--bootstrap-servers",
                "localhost:29092",
            ]
        )
        self.assertEqual(args.group_id, "s8844-writer")
        self.assertEqual(args.topic, TASKS_TOPIC)
        self.assertEqual(args.dead_letter_topic, "s8844_dead_letter")
        self.assertEqual(args.bootstrap_servers, "localhost:29092")
        self.assertEqual(args.max_attempts, 3)
        self.assertFalse(args.live)

    def test_poison_harness_later_valid_check_is_explicit(self) -> None:
        args = parse_poison_harness_args(
            [
                "--validate-args",
                "--later-valid-check",
                "--group-id",
                "s8844-writer",
                "--topic",
                "s8844_tasks",
                "--dead-letter-topic",
                "s8844_dead_letter",
            ]
        )
        self.assertTrue(args.later_valid_check)
        self.assertEqual(args.group_id, "s8844-writer")
        self.assertEqual(args.topic, "s8844_tasks")

    def test_homework_demo_configuration_is_host_side_and_no_retry(self) -> None:
        args = parse_homework_demo_args(
            ["--base-url", "http://127.0.0.1:8744"]
        )
        self.assertEqual(args.base_url, "http://127.0.0.1:8744")

    def test_agent_demo_configuration_is_single_publish(self) -> None:
        args = parse_agent_demo_args(
            ["--bootstrap-servers", "localhost:29092"]
        )
        self.assertEqual(args.bootstrap_servers, "localhost:29092")

    def test_consumer_death_readiness_and_event_contract(self) -> None:
        class TopicPartition:
            def __init__(self, topic: str) -> None:
                self.topic = topic

        class Assignment:
            topic_partitions = (TopicPartition(TASKS_TOPIC),)

        class Member:
            assignment = Assignment()

        class Description:
            group_id = "s8844-writer"
            state = "STABLE"
            members = (Member(),)

        self.assertTrue(group_ready(Description()))
        snapshot = readiness_snapshot(Description())
        self.assertTrue(snapshot["ready"])
        self.assertEqual(snapshot["assigned_topics"], [TASKS_TOPIC])
        event = death_event(
            "pre_commit_crash",
            correlation_id="death-1",
            topic=TASKS_TOPIC,
            partition=0,
            offset=7,
            process="writer-1",
            timestamp="offline",
            committed=False,
            crash_point=CRASH_POINT,
        )
        self.assertFalse(event["committed"])
        self.assertEqual(expected_consumer_death_sequence()[1], event["event_type"])

    def test_consumer_death_harness_arguments_are_explicit(self) -> None:
        args = parse_harness_args(
            [
                "--validate-args",
                "--group-id",
                "s8844-writer",
                "--topic",
                "s8844_tasks",
            ]
        )
        self.assertEqual(args.group_id, "s8844-writer")
        self.assertEqual(args.topic, "s8844_tasks")
        self.assertFalse(args.live)

    def test_harness_producer_constructor_has_no_unsupported_retries_keyword(self) -> None:
        captured: dict[str, object] = {}

        class FakeProducer:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)

        async def construct() -> object:
            with patch(
                "hw08_kafka_runtime.require_aiokafka",
                return_value=(object, FakeProducer),
            ):
                return await build_producer(bootstrap_servers="localhost:29092")

        self.assertIsInstance(asyncio.run(construct()), FakeProducer)
        self.assertEqual(captured["bootstrap_servers"], "localhost:29092")
        self.assertNotIn("retries", captured)

    def test_group_description_normalizes_list_and_mapping_responses(self) -> None:
        class Description:
            group = "s8844-writer"
            state = "STABLE"
            members = ({"member_id": "m1", "assignment": {"topic_partitions": {b"s8844_tasks": [0, 1]}}},)

        description = Description()
        self.assertIs(normalize_group_description([description], "s8844-writer"), description)
        self.assertIs(
            normalize_group_description({"s8844-writer": description}, "s8844-writer"),
            description,
        )
        self.assertIsNone(normalize_group_description([description], "other-group"))
        self.assertTrue(group_ready(description))
        snapshot = readiness_snapshot(description)
        self.assertEqual(snapshot["active_member_count"], 1)
        self.assertEqual(snapshot["assigned_topics"], ["s8844_tasks"])

    def test_group_description_normalizes_aiokafka_response_wrapper(self) -> None:
        response = {
            "groups": [
                {
                    "group": b"s8844-writer",
                    "state": b"STABLE",
                    "members": [
                        {
                            "member_id": "writer-1",
                            "member_assignment": {
                                "assignment": [(b"s8844_tasks", [0, 1])]
                            },
                        }
                    ],
                }
            ]
        }
        description = normalize_group_description([response], "s8844-writer")
        self.assertIsNotNone(description)
        self.assertTrue(group_ready(description))
        self.assertEqual(assignment_topics(description), {"s8844_tasks"})

    def test_realistic_aiokafka_tuple_response_decodes_two_members(self) -> None:
        def encoded_assignment(topic: str, partition: int) -> bytes:
            topic_bytes = topic.encode("utf-8")
            return (
                struct.pack(">hih", 0, 1, len(topic_bytes))
                + topic_bytes
                + struct.pack(">i", 1)
                + struct.pack(">i", partition)
                + struct.pack(">i", 0)
            )

        group_entry = (
            0,
            "s8844-writer",
            "STABLE",
            "consumer",
            "range",
            [
                ("writer-1", "client", "host", b"", encoded_assignment("s8844_tasks", 0)),
                ("writer-2", "client", "host", b"", encoded_assignment("s8844_tasks", 1)),
            ],
            0,
        )

        class DescribeGroupsResponse:
            groups = [group_entry]

        description = normalize_group_description(
            [DescribeGroupsResponse()], "s8844-writer"
        )
        self.assertEqual(description["group"], "s8844-writer")
        self.assertEqual(description["state"], "STABLE")
        self.assertEqual(len(description["members"]), 2)
        self.assertTrue(group_ready(description))
        self.assertEqual(assignment_topics(description), {"s8844_tasks"})

    def test_realistic_aiokafka_v2_six_field_group_tuple(self) -> None:
        group_entry = (
            0,
            "s8844-writer",
            "STABLE",
            "consumer",
            "range",
            [
                ("writer-1", "client", "host", b"", b""),
                ("writer-2", "client", "host", b"", b""),
            ],
        )

        class DescribeGroupsResponseV2:
            groups = [group_entry]

        description = normalize_group_description(
            [DescribeGroupsResponseV2()], "s8844-writer"
        )
        self.assertEqual(description["group"], "s8844-writer")
        self.assertEqual(description["state"], "STABLE")
        self.assertEqual(len(description["members"]), 2)

    def test_ambiguous_tuple_fails_safely(self) -> None:
        with self.assertRaises(ValueError):
            normalize_group_description(
                [{"groups": [(0, "s8844-writer")] }], "s8844-writer"
            )

    def test_writer_crash_hook_is_one_shot_and_stage_event_is_safe(self) -> None:
        import os
        import tempfile

        class Record:
            topic = "s8844_tasks"
            partition = 0
            offset = 4

        with tempfile.TemporaryDirectory() as directory:
            marker = os.path.join(directory, "used")
            prior = os.environ.get("HW8_CRASH_BEFORE_COMMIT_ONCE")
            os.environ["HW8_CRASH_BEFORE_COMMIT_ONCE"] = "1"
            try:
                self.assertTrue(crash_once_before_commit(stage="writer", marker_path=marker))
                self.assertFalse(crash_once_before_commit(stage="writer", marker_path=marker))
            finally:
                if prior is None:
                    os.environ.pop("HW8_CRASH_BEFORE_COMMIT_ONCE", None)
                else:
                    os.environ["HW8_CRASH_BEFORE_COMMIT_ONCE"] = prior
        event = stage_event(
            "message_received",
            stage="writer",
            record=Record(),
            message={"correlation_id": "death-1"},
            committed=False,
        )
        self.assertEqual(event["offset"], 4)
        self.assertEqual(event["correlation_id"], "death-1")

    def test_cli_fallback_requires_stable_assigned_output(self) -> None:
        state = "GROUP STATE\ns8844-writer STABLE\n"
        describe = (
            "GROUP TOPIC PARTITION CURRENT-OFFSET LOG-END-OFFSET LAG CONSUMER-ID HOST CLIENT-ID\n"
            "s8844-writer s8844_tasks 0 - 0 - member-1 host client\n"
        )
        result = parse_cli_readiness(state, describe)
        self.assertTrue(result["ready"])
        self.assertIsNone(parse_cli_readiness("", describe))
        self.assertIsNone(parse_cli_readiness(state, ""))

    def test_response_diagnostic_exposes_safe_shape_only(self) -> None:
        diagnostic = response_diagnostic([{"groups": []}], "s8844-writer")
        self.assertEqual(diagnostic["raw_response_type"], "list")
        self.assertIn("outer_item_shapes", diagnostic)
        self.assertNotIn("password", str(diagnostic).lower())

    def test_admin_failure_immediately_uses_cli_fallback(self) -> None:
        class FailingAdmin:
            async def describe_consumer_groups(self, group_ids):
                raise TimeoutError("mock admin timeout")

        calls = []

        def fallback_probe(**kwargs):
            calls.append(kwargs)
            return {
                "group_id": "s8844-writer",
                "group_state": "STABLE",
                "active_member_count": 2,
                "assigned_topics": ["s8844_tasks"],
                "required_topic": "s8844_tasks",
                "ready": True,
                "readiness_method": "kafka_cli_fallback",
            }

        result = asyncio.run(
            wait_for_writer_group(
                admin_client=FailingAdmin(),
                fallback_probe=fallback_probe,
                timeout_seconds=1,
                poll_seconds=0.01,
            )
        )
        self.assertEqual(result["readiness_method"], "kafka_cli_fallback")
        self.assertEqual(calls[0]["group_id"], "s8844-writer")

    def test_cli_failure_never_returns_ready(self) -> None:
        self.assertIsNone(
            parse_cli_readiness(
                "GROUP STATE\ns8844-writer UNKNOWN\n",
                "s8844-writer s8844_tasks 0 - 0 - member-1 host client\n",
            )
        )

    def test_ordering_generation_is_exactly_twenty_and_recordable(self) -> None:
        unkeyed = generate_ordering_messages(keyed=False)
        keyed = generate_ordering_messages(keyed=True)
        self.assertEqual(len(unkeyed), 20)
        self.assertEqual(len(keyed), 20)
        self.assertTrue(all(item["key"] is None for item in unkeyed))
        self.assertEqual(len({item["key"] for item in keyed}), 1)
        record = record_processing(
            partition=1,
            offset=4,
            consumer="writer-2",
            sequence=3,
            key=keyed[3]["key"],
            processing_order=1,
        )
        self.assertEqual(records_to_rows([record])[0]["sequence"], 3)

    def test_ordering_harness_requires_seed_count_and_topic(self) -> None:
        args = parse_ordering_args(
            [
                "--validate-args",
                "--mode",
                "keyed",
                "--bootstrap-servers",
                "localhost:29092",
            ]
        )
        self.assertEqual(args.seed, 268844)
        self.assertEqual(args.count, 20)
        self.assertEqual(args.topic, "s8844_tasks")
        self.assertEqual(args.group_id, "s8844-writer")
        self.assertFalse(args.live)

    def test_ordering_partition_response_is_synchronous_and_exactly_two(self) -> None:
        self.assertEqual(require_exact_two_partitions({0, 1}), [0, 1])
        with self.assertRaises(RuntimeError):
            require_exact_two_partitions({0})
        with self.assertRaises(RuntimeError):
            require_exact_two_partitions({0, 1, 2})
        with self.assertRaises(RuntimeError):
            require_exact_two_partitions("invalid")

    def test_ordering_metadata_consumer_normal_cleanup(self) -> None:
        class Consumer:
            def __init__(self) -> None:
                self.started = False
                self.stopped = False

            async def start(self) -> None:
                self.started = True

            def partitions_for_topic(self, topic: str) -> set[int]:
                return {0, 1}

            async def stop(self) -> None:
                self.stopped = True

        consumer = Consumer()
        self.assertEqual(asyncio.run(read_topic_partitions(consumer, "s8844_tasks")), [0, 1])
        self.assertTrue(consumer.started)
        self.assertTrue(consumer.stopped)

    def test_ordering_metadata_cleanup_cancellation_does_not_mask_result(self) -> None:
        class Consumer:
            async def start(self) -> None:
                return None

            def partitions_for_topic(self, topic: str) -> set[int]:
                return {0, 1}

            async def stop(self) -> None:
                raise asyncio.CancelledError()

        self.assertEqual(asyncio.run(read_topic_partitions(Consumer(), "s8844_tasks")), [0, 1])

    def test_ordering_partial_start_failure_still_cleans_up_and_preserves_error(self) -> None:
        class Consumer:
            def __init__(self) -> None:
                self.stopped = False

            async def start(self) -> None:
                raise RuntimeError("startup failed")

            def partitions_for_topic(self, topic: str) -> set[int]:
                return {0, 1}

            async def stop(self) -> None:
                self.stopped = True

        consumer = Consumer()
        with self.assertRaisesRegex(RuntimeError, "startup failed"):
            asyncio.run(read_topic_partitions(consumer, "s8844_tasks"))
        self.assertTrue(consumer.stopped)

    def test_ordering_partition_error_is_preserved_when_cleanup_is_cancelled(self) -> None:
        class Consumer:
            async def start(self) -> None:
                return None

            def partitions_for_topic(self, topic: str) -> set[int]:
                return {0}

            async def stop(self) -> None:
                raise asyncio.CancelledError()

        with self.assertRaisesRegex(RuntimeError, "exactly partitions"):
            asyncio.run(read_topic_partitions(Consumer(), "s8844_tasks"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

