export type NotePublicationStatus = "pending" | "published" | "unknown";

export interface NoteHistoryRow {
  attempt_id: string;
  content_hash: string;
  content: string;
  status: NotePublicationStatus;
  note_id: string | null;
  note_url: string | null;
  attempted_at: string;
  published_at: string | null;
  updated_at: string;
}

export interface NoteReservation {
  attemptId: string;
  contentHash: string;
  content: string;
  attemptedAt: string;
}

export class DuplicateNoteError extends Error {
  readonly existing: NoteHistoryRow;

  constructor(existing: NoteHistoryRow) {
    super(
      `Duplicate Note blocked: identical normalized text already has status=${existing.status}. Create a substantively different Note.`,
    );
    this.name = "DuplicateNoteError";
    this.existing = existing;
  }
}

export function normalizeNoteText(text: string): string {
  return text
    .normalize("NFKC")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim().replace(/[\t ]+/g, " "))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export async function hashNoteText(text: string): Promise<string> {
  const normalized = normalizeNoteText(text);
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(normalized));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function reserveNote(
  db: D1Database,
  text: string,
  now = new Date(),
): Promise<NoteReservation> {
  const content = normalizeNoteText(text);
  if (!content) {
    throw new Error("Note body must not be empty");
  }

  const contentHash = await hashNoteText(content);
  const attemptId = crypto.randomUUID();
  const attemptedAt = now.toISOString();
  const inserted = await db
    .prepare(
      `INSERT OR IGNORE INTO note_publications
       (attempt_id, content_hash, content, status, attempted_at, updated_at)
       VALUES (?, ?, ?, 'pending', ?, ?)`,
    )
    .bind(attemptId, contentHash, content, attemptedAt, attemptedAt)
    .run();

  if ((inserted.meta.changes ?? 0) !== 1) {
    const existing = await db
      .prepare(
        `SELECT attempt_id, content_hash, content, status, note_id, note_url,
                attempted_at, published_at, updated_at
         FROM note_publications WHERE content_hash = ?`,
      )
      .bind(contentHash)
      .first<NoteHistoryRow>();
    if (existing) {
      throw new DuplicateNoteError(existing);
    }
    throw new Error("Note history reservation was not created");
  }

  return { attemptId, contentHash, content, attemptedAt };
}

export async function markNotePublished(
  db: D1Database,
  reservation: NoteReservation,
  noteId: string | null,
  noteUrl: string | null,
  now = new Date(),
): Promise<void> {
  const publishedAt = now.toISOString();
  await db
    .prepare(
      `UPDATE note_publications
       SET status = 'published', note_id = ?, note_url = ?, published_at = ?, updated_at = ?
       WHERE attempt_id = ?`,
    )
    .bind(noteId, noteUrl, publishedAt, publishedAt, reservation.attemptId)
    .run();
}

export async function markNoteUnknown(
  db: D1Database,
  reservation: NoteReservation,
  now = new Date(),
): Promise<void> {
  await db
    .prepare(
      `UPDATE note_publications
       SET status = 'unknown', updated_at = ?
       WHERE attempt_id = ? AND status = 'pending'`,
    )
    .bind(now.toISOString(), reservation.attemptId)
    .run();
}

export async function listNoteHistory(db: D1Database, limit: number): Promise<NoteHistoryRow[]> {
  const response = await db
    .prepare(
      `SELECT attempt_id, content_hash, content, status, note_id, note_url,
              attempted_at, published_at, updated_at
       FROM note_publications
       ORDER BY attempted_at DESC
       LIMIT ?`,
    )
    .bind(limit)
    .all<NoteHistoryRow>();
  return response.results;
}
