"""One-off: copy course 243 (Module 1, org 327) + slides + RAG doc to org 1."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.database import engine  # noqa: E402

SRC_COURSE, SRC_DOC, DST_ORG, ADMIN_ID = 243, 50, 1, 1


def cols(cur, table, exclude):
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name=%s "
        "ORDER BY ordinal_position", (table,))
    return [r[0] for r in cur.fetchall() if r[0] not in exclude]


def main():
    raw = engine.raw_connection()
    cur = raw.cursor()

    c = cols(cur, "courses", {"id", "organization_id", "created_by_id"})
    cur.execute(
        f'INSERT INTO courses (organization_id, created_by_id, {", ".join(c)}) '
        f'SELECT %s, %s, {", ".join(c)} FROM courses WHERE id=%s RETURNING id',
        (DST_ORG, ADMIN_ID, SRC_COURSE))
    new_course = cur.fetchone()[0]

    s = cols(cur, "course_slides", {"id", "course_id"})
    cur.execute(
        f'INSERT INTO course_slides (course_id, {", ".join(s)}) '
        f'SELECT %s, {", ".join(s)} FROM course_slides WHERE course_id=%s',
        (new_course, SRC_COURSE))
    n_slides = cur.rowcount

    d = cols(cur, "source_documents",
             {"id", "organization_id", "course_id", "uploaded_by_id"})
    cur.execute(
        f'INSERT INTO source_documents (organization_id, course_id, '
        f'uploaded_by_id, {", ".join(d)}) '
        f'SELECT %s, %s, %s, {", ".join(d)} FROM source_documents WHERE id=%s '
        f'RETURNING id',
        (DST_ORG, new_course, ADMIN_ID, SRC_DOC))
    new_doc = cur.fetchone()[0]

    k = cols(cur, "source_chunks", {"id", "document_id"})
    cur.execute(
        f'INSERT INTO source_chunks (document_id, {", ".join(k)}) '
        f'SELECT %s, {", ".join(k)} FROM source_chunks WHERE document_id=%s',
        (new_doc, SRC_DOC))
    n_chunks = cur.rowcount

    raw.commit()
    print(f"new course id={new_course}, slides={n_slides}, "
          f"doc id={new_doc}, chunks={n_chunks}")
    raw.close()


if __name__ == "__main__":
    main()
