from models import LiveSession


def resolve_certificate_title(c, sessions: dict) -> str:
    if c.type == "LIVE_SESSION_ATTENDANCE" and c.live_session_id in sessions:
        return sessions[c.live_session_id].title
    return c.course.title if c.course else None
