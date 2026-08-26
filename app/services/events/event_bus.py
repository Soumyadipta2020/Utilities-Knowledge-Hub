import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

class EventBus:
    """
    In-process Event Bus for the Utilities Knowledge Hub.
    In an enterprise deployment, this would be replaced by Kafka, Azure Event Hubs,
    AWS EventBridge, or Google Pub/Sub.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        # We also maintain a queue for async consumption if needed
        self._queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]):
        """Subscribe a synchronous callback to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, request_id: str, user_id: str, metadata: Dict[str, Any]):
        """Publish an event to the bus."""
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "request_id": request_id,
            "user_id": user_id,
            "metadata": metadata
        }
        
        # Fire synchronous callbacks immediately for tracing/logging purposes
        for callback in self._subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event subscriber for {event_type}: {e}")
                
        # Also push to async queue for potential decoupled processing
        try:
            self._queue.put_nowait(event)
        except Exception as e:
            logger.error(f"Failed to enqueue event {event_type}: {e}")

    async def _worker(self):
        self._running = True
        while self._running:
            try:
                event = await self._queue.get()
                # Default behavior is just to log, but in enterprise this would push to Kafka
                # logger.debug(f"EventBus Async Processed: {event['event_type']} - {event['request_id']}")
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EventBus worker error: {e}")

    def start(self):
        """Start the background async worker if running in an event loop."""
        if self._worker_task is None:
            try:
                loop = asyncio.get_running_loop()
                self._worker_task = loop.create_task(self._worker())
            except RuntimeError:
                pass # No running loop, will just rely on synchronous callbacks

    def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()

# Global event bus instance
event_bus = EventBus()
