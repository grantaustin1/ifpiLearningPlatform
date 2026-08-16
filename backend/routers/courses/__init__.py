"""Courses router package — import order preserves route matching."""
from routers.courses.common import router  # noqa: F401
from routers.courses import crud, ratings  # noqa: F401,E402
from routers.courses.slides import richtext_router  # noqa: F401
from routers.courses.enrollment import (  # noqa: F401
    complete_course, enroll,
)
from routers.courses import prerequisites  # noqa: F401
