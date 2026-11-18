
import unittest

from intelligence.incident_correlator import (
    correlate_events,
    build_incident,
)


def make_event(
    event_id,
    machine="IGGY",
    resource="memory",
    detected_at="2026-11-14T09:00:00+00:00"
):
    return {
        "event_id": event_id,
        "event_type": "RESOURCE_ANOMALY",
        "machine": machine,
        "resource": resource,
        "detected_at": detected_at,
        "started_at": detected_at,
    }


class TestIncidentCorrelation(unittest.TestCase):

    def test_same_machine_events_within_window_are_grouped(self):
        events = [
            make_event(
                "event-1",
                detected_at="2026-11-14T09:00:00+00:00"
            ),
            make_event(
                "event-2",
                resource="cpu",
                detected_at="2026-11-14T09:03:00+00:00"
            ),
        ]

        groups = correlate_events(events)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)

    def test_different_machines_are_separated(self):
        events = [
            make_event("event-1", machine="IGGY"),
            make_event(
                "event-2",
                machine="SERVER-2",
                detected_at="2026-11-14T09:01:00+00:00"
            ),
        ]

        groups = correlate_events(events)

        self.assertEqual(len(groups), 2)

    def test_events_outside_window_are_separated(self):
        events = [
            make_event(
                "event-1",
                detected_at="2026-11-14T09:00:00+00:00"
            ),
            make_event(
                "event-2",
                detected_at="2026-11-14T09:06:00+00:00"
            ),
        ]

        groups = correlate_events(events)

        self.assertEqual(len(groups), 2)

    def test_interleaved_machines_are_grouped_correctly(self):
        events = [
            make_event(
                "event-1",
                machine="IGGY",
                detected_at="2026-11-14T09:00:00+00:00"
            ),
            make_event(
                "event-2",
                machine="SERVER-2",
                detected_at="2026-11-14T09:01:00+00:00"
            ),
            make_event(
                "event-3",
                machine="IGGY",
                resource="cpu",
                detected_at="2026-11-14T09:02:00+00:00"
            ),
        ]

        groups = correlate_events(events)

        iggy_groups = [
            group for group in groups
            if group[0]["machine"] == "IGGY"
        ]

        self.assertEqual(len(iggy_groups), 1)
        self.assertEqual(len(iggy_groups[0]), 2)

    def test_incident_contains_correct_resources(self):
        events = [
            make_event("event-1", resource="memory"),
            make_event(
                "event-2",
                resource="cpu",
                detected_at="2026-11-14T09:01:00+00:00"
            ),
        ]

        incident = build_incident(events)

        self.assertEqual(
            incident["affected_resources"],
            ["cpu", "memory"]
        )

        self.assertEqual(incident["event_count"], 2)
        self.assertEqual(incident["severity"], "HIGH")


if __name__ == "__main__":
    unittest.main()
