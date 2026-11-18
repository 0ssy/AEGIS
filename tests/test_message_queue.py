
import tempfile
import unittest
from pathlib import Path

from backend.message_queue import AegisMessageQueue


class TestAegisMessageQueue(unittest.TestCase):

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database = Path(self.temp_directory.name) / "test_queue.db"
        self.queue = AegisMessageQueue(database)

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_enqueue_message(self):
        message_id = self.queue.enqueue({
            "machine": "IGGY",
            "cpu": 25.5
        })

        self.assertIsNotNone(message_id)

        stats = self.queue.get_queue_stats()
        self.assertEqual(stats["queued"], 1)

    def test_receive_message(self):
        self.queue.enqueue({"machine": "IGGY"})

        messages = self.queue.receive_messages()

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["body"]["machine"], "IGGY")
        self.assertEqual(messages[0]["attempts"], 1)

    def test_acknowledge_message(self):
        message_id = self.queue.enqueue({"machine": "IGGY"})

        messages = self.queue.receive_messages()

        result = self.queue.acknowledge(message_id)

        self.assertTrue(result)
        self.assertEqual(self.queue.get_queue_stats()["total"], 0)

    def test_release_message(self):
        message_id = self.queue.enqueue({"machine": "IGGY"})

        self.queue.receive_messages()

        result = self.queue.release(message_id)

        self.assertTrue(result)

        messages = self.queue.receive_messages()

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["attempts"], 2)

    def test_invalid_message(self):
        with self.assertRaises(ValueError):
            self.queue.enqueue("invalid")

    def test_receive_empty_queue(self):
        messages = self.queue.receive_messages()

        self.assertEqual(messages, [])

    def test_multiple_messages(self):
        self.queue.enqueue({"machine": "IGGY"})
        self.queue.enqueue({"machine": "IGGY-2"})
        self.queue.enqueue({"machine": "IGGY-3"})

        messages = self.queue.receive_messages(max_messages=3)

        self.assertEqual(len(messages), 3)

    def test_invalid_visibility_timeout(self):
        with self.assertRaises(ValueError):
            self.queue.receive_messages(visibility_timeout=0)


if __name__ == "__main__":
    unittest.main()
