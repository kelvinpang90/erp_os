from app.events.base import DomainEvent, EventBus

event_bus = EventBus()

__all__ = ["DomainEvent", "EventBus", "event_bus"]
