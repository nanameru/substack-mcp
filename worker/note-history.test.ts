import assert from "node:assert/strict";
import test from "node:test";

import {
  DuplicateNoteError,
  hashNoteText,
  listNoteHistory,
  markNotePublished,
  markNoteUnknown,
  normalizeNoteText,
  reserveNote,
  type NoteHistoryRow,
} from "./note-history.ts";

class FakeD1 {
  rows = new Map<string, NoteHistoryRow>();

  prepare(sql: string) {
    const database = this;
    let values: unknown[] = [];
    return {
      bind(...bound: unknown[]) {
        values = bound;
        return this;
      },
      async run() {
        if (sql.includes("INSERT OR IGNORE")) {
          const [attemptId, contentHash, content, attemptedAt, updatedAt] = values as string[];
          if ([...database.rows.values()].some((row) => row.content_hash === contentHash)) {
            return { success: true, meta: { changes: 0 } };
          }
          database.rows.set(attemptId, {
            attempt_id: attemptId,
            content_hash: contentHash,
            content,
            status: "pending",
            note_id: null,
            note_url: null,
            attempted_at: attemptedAt,
            published_at: null,
            updated_at: updatedAt,
          });
          return { success: true, meta: { changes: 1 } };
        }
        if (sql.includes("status = 'published'")) {
          const [noteId, noteUrl, publishedAt, updatedAt, attemptId] = values as string[];
          const row = database.rows.get(attemptId)!;
          Object.assign(row, {
            status: "published",
            note_id: noteId,
            note_url: noteUrl,
            published_at: publishedAt,
            updated_at: updatedAt,
          });
          return { success: true, meta: { changes: 1 } };
        }
        if (sql.includes("status = 'unknown'")) {
          const [updatedAt, attemptId] = values as string[];
          const row = database.rows.get(attemptId)!;
          if (row.status === "pending") {
            row.status = "unknown";
            row.updated_at = updatedAt;
          }
          return { success: true, meta: { changes: 1 } };
        }
        throw new Error(`Unexpected run query: ${sql}`);
      },
      async first() {
        const [contentHash] = values as string[];
        return [...database.rows.values()].find((row) => row.content_hash === contentHash) ?? null;
      },
      async all() {
        const [limit] = values as number[];
        return {
          success: true,
          results: [...database.rows.values()]
            .sort((a, b) => b.attempted_at.localeCompare(a.attempted_at))
            .slice(0, limit),
          meta: {},
        };
      },
    };
  }
}

test("normalizes harmless whitespace before hashing", async () => {
  const first = " AI開発では\r\n\r\n  外部状態も確認する。 ";
  const second = "AI開発では\n\n外部状態も確認する。";
  assert.equal(normalizeNoteText(first), second);
  assert.equal(await hashNoteText(first), await hashNoteText(second));
});

test("reserves once and blocks an identical normalized body", async () => {
  const db = new FakeD1();
  await reserveNote(db as unknown as D1Database, "同じ Note", new Date("2026-09-12T00:00:00Z"));
  await assert.rejects(
    reserveNote(db as unknown as D1Database, "  同じ   Note  ", new Date("2026-09-12T00:01:00Z")),
    DuplicateNoteError,
  );
  assert.equal(db.rows.size, 1);
});

test("records published metadata and returns newest history first", async () => {
  const db = new FakeD1();
  const first = await reserveNote(
    db as unknown as D1Database,
    "最初のNote",
    new Date("2026-09-12T00:00:00Z"),
  );
  await markNotePublished(
    db as unknown as D1Database,
    first,
    "123",
    "https://substack.com/note/c-123",
    new Date("2026-09-12T00:00:10Z"),
  );
  await reserveNote(
    db as unknown as D1Database,
    "次のNote",
    new Date("2026-09-12T01:00:00Z"),
  );

  const history = await listNoteHistory(db as unknown as D1Database, 2);
  assert.deepEqual(
    history.map((row) => row.content),
    ["次のNote", "最初のNote"],
  );
  assert.equal(history[1].status, "published");
  assert.equal(history[1].note_id, "123");
});

test("marks an uncertain upstream result as unknown", async () => {
  const db = new FakeD1();
  const reservation = await reserveNote(
    db as unknown as D1Database,
    "結果不明のNote",
    new Date("2026-09-12T00:00:00Z"),
  );
  await markNoteUnknown(
    db as unknown as D1Database,
    reservation,
    new Date("2026-09-12T00:00:30Z"),
  );
  assert.equal(db.rows.get(reservation.attemptId)?.status, "unknown");
  await assert.rejects(
    reserveNote(db as unknown as D1Database, "結果不明のNote"),
    DuplicateNoteError,
  );
});
