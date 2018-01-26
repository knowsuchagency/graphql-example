from contextlib import contextmanager

from eliot import start_action, Message

from aiohttp import web

@contextmanager
def log_action(action_type: str, **kwargs):
    """A simple wrapper over eliot.start_action to make things less verbose."""
    with start_action(action_type=action_type, **kwargs) as action:
        yield action


@contextmanager
def log_request(request: web.Request, **kwargs):
    """A logging shortcut for when we receive requests."""
    with log_action(
        'processing request',

        method=request.method,
        resource=str(request.rel_url),
        https_enabled=request.secure,
        from_ip=request.remote,
        query=dict(request.query) or None,

        **kwargs

    ) as action:
        yield action


@contextmanager
def log_response(response: web.Response, **kwargs):
    with log_action(
        'sending response',

        status=response.status,
        headers=dict(response.headers),

        **kwargs

    ) as action:
        yield action


def log_message(message: str, **kwargs):
    """Log the message in the current action context."""
    Message.log(message_type=message, **kwargs)
