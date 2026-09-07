"""Incremental document indexing and explained local search."""

from __future__ import annotations
import difflib
import json
import re
import sqlite3
from pathlib import Path
from localdesk.jobs import utcnow
from localdesk.parsers import extract
from localdesk.safety import (
    DEFAULT_EXCLUDES,
    InputError,
    MAX_FILE_BYTES,
    checked_path,
    digest,
    walk_files,
    within,
)


def query_tokens(query: str) -> list[str]:
    # User strings cannot inject FTS operators, SQL, or markup.
    return re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE)[:20]


class Index:
    def __init__(self, store, private_data: Path):
        self.store, self.private_data = store, private_data
        from localdesk.semantic import SearchCache

        self.semantic_cache = SearchCache()
        with store.connection() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS roots(
                    id INTEGER PRIMARY KEY,path TEXT UNIQUE,name TEXT,patterns TEXT,ocr INTEGER DEFAULT 0,
                    last_scan TEXT,last_error TEXT);
                CREATE TABLE IF NOT EXISTS files(
                    id INTEGER PRIMARY KEY,root_id INTEGER REFERENCES roots(id) ON DELETE CASCADE,
                    path TEXT UNIQUE,name TEXT,extension TEXT,size INTEGER,mtime INTEGER,
                    sha256 TEXT,text TEXT,method TEXT,warning TEXT,indexed TEXT,tags TEXT DEFAULT '[]');
                CREATE INDEX IF NOT EXISTS files_root ON files(root_id);
                CREATE INDEX IF NOT EXISTS files_hash ON files(sha256);
                CREATE INDEX IF NOT EXISTS files_extension ON files(extension);
                CREATE TABLE IF NOT EXISTS saved_searches(
                    id INTEGER PRIMARY KEY,name TEXT UNIQUE,query TEXT,extension TEXT,tag TEXT);
            """
            )
            try:
                db.execute(
                    'CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(filename,path,body,tokenize="unicode61")'
                )
                db.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS search_vocabulary USING fts5vocab(search_index,row)"
                )
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False

    def add_root(
        self, value: str, patterns: list[str] | None = None, ocr: bool = False
    ) -> dict:
        path = checked_path(value, directory=True)
        if within(path, self.private_data):
            raise InputError("Do not index the app data directory.")
        if patterns is None:
            patterns = list(DEFAULT_EXCLUDES)
        if (
            not isinstance(patterns, list)
            or len(patterns) > 80
            or any(not isinstance(p, str) or len(p) > 150 for p in patterns)
        ):
            raise InputError("Use at most 80 short folder or file exclusion patterns.")
        # Default exclusions cannot be removed accidentally through an imported setting.
        patterns = list(dict.fromkeys([*DEFAULT_EXCLUDES, *patterns]))
        existing = self.store.one("SELECT * FROM roots WHERE path=?", (str(path),))
        if existing:
            return existing
        for other in self.store.rows("SELECT path FROM roots"):
            if within(path, Path(other["path"])) or within(Path(other["path"]), path):
                raise InputError(
                    "Indexed folders must not overlap. Remove the existing root first."
                )
        ident = self.store.execute(
            "INSERT INTO roots(path,name,patterns,ocr) VALUES(?,?,?,?)",
            (str(path), path.name or str(path), json.dumps(patterns), int(ocr)),
        )
        return self.store.one("SELECT * FROM roots WHERE id=?", (ident,))

    def remove_root(self, ident: int) -> None:
        with self.store.connection() as db:
            if self.fts:
                db.execute(
                    "DELETE FROM search_index WHERE rowid IN (SELECT id FROM files WHERE root_id=?)",
                    (ident,),
                )
            db.execute("DELETE FROM roots WHERE id=?", (ident,))

    def scan(self, ident: int, context, *, force: bool = False) -> dict:
        root = self.store.one("SELECT * FROM roots WHERE id=?", (ident,))
        if root is None:
            raise InputError("This indexed folder does not exist.")
        folder = checked_path(root["path"], directory=True)
        context.progress(1, "Listing the selected folder.")
        files = [
            p
            for p in walk_files(folder, patterns=json.loads(root["patterns"]))
            if not within(p, self.private_data)
        ]
        seen, changed, skipped, warnings = set(), 0, 0, []
        for offset, path in enumerate(files):
            context.check()
            stat = path.stat()
            source = str(path)
            seen.add(source)
            context.progress(
                2 + int(92 * offset / max(len(files), 1)), f"Indexing {path.name}"
            )
            prior = self.store.one(
                "SELECT id,mtime,size,sha256 FROM files WHERE path=?", (source,)
            )
            if (
                not force
                and prior
                and prior["mtime"] == stat.st_mtime_ns
                and prior["size"] == stat.st_size
            ):
                skipped += 1
                continue
            text, method, warning, sha = "", "Filename only", "", ""
            if stat.st_size > MAX_FILE_BYTES:
                warning = "File exceeds 25 MiB. Only its filename and path are indexed."
            else:
                sha = digest(path)
                try:
                    parsed = extract(path, ocr=bool(root["ocr"]))
                    text, method = parsed["text"], parsed["method"]
                    warning = " ".join(parsed["warnings"])
                    if parsed["truncated"]:
                        warning += " Text was limited to 250,000 characters."
                except Exception as exc:
                    warning = str(exc)[:300]
            after = path.stat()
            if (stat.st_mtime_ns, stat.st_size) != (after.st_mtime_ns, after.st_size):
                warnings.append(
                    {
                        "name": path.name,
                        "warning": "File changed during indexing. Scan again.",
                    }
                )
                continue
            if warning:
                warnings.append({"name": path.name, "warning": warning})
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO files(root_id,path,name,extension,size,mtime,sha256,text,method,warning,indexed) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET "
                    "root_id=excluded.root_id,name=excluded.name,extension=excluded.extension,size=excluded.size,"
                    "mtime=excluded.mtime,sha256=excluded.sha256,text=excluded.text,method=excluded.method,"
                    "warning=excluded.warning,indexed=excluded.indexed",
                    (
                        ident,
                        source,
                        path.name,
                        path.suffix.lower(),
                        stat.st_size,
                        stat.st_mtime_ns,
                        sha,
                        text,
                        method,
                        warning,
                        utcnow(),
                    ),
                )
                file_id = db.execute(
                    "SELECT id FROM files WHERE path=?", (source,)
                ).fetchone()[0]
                if self.fts:
                    db.execute("DELETE FROM search_index WHERE rowid=?", (file_id,))
                    db.execute(
                        "INSERT INTO search_index(rowid,filename,path,body) VALUES(?,?,?,?)",
                        (file_id, path.name, source, text),
                    )
            changed += 1
        context.check()
        # Only prune after a complete directory listing and processing pass.
        stale = [
            row["id"]
            for row in self.store.rows(
                "SELECT id,path FROM files WHERE root_id=?", (ident,)
            )
            if row["path"] not in seen
        ]
        with self.store.connection() as db:
            for file_id in stale:
                if self.fts:
                    db.execute("DELETE FROM search_index WHERE rowid=?", (file_id,))
                db.execute("DELETE FROM files WHERE id=?", (file_id,))
            db.execute(
                "UPDATE roots SET last_scan=?,last_error=? WHERE id=?",
                (
                    utcnow(),
                    f"{len(warnings)} files need a coverage check." if warnings else "",
                    ident,
                ),
            )
        return {
            "folder": str(folder),
            "found": len(files),
            "updated": changed,
            "unchanged": skipped,
            "removed_from_index": len(stale),
            "warnings": warnings,
            "search_engine": "FTS5" if self.fts else "text match",
        }

    def search(
        self,
        query: str = "",
        *,
        extension: str = "",
        tag: str = "",
        root: int | None = None,
        limit: int = 100,
    ) -> dict:
        tokens = query_tokens(query)
        where, args = [], []
        if tokens and self.fts:
            source = "search_index JOIN files f ON f.id=search_index.rowid"
            where.append("search_index MATCH ?")
            args.append(
                " AND ".join('"' + word.replace('"', '""') + '"*' for word in tokens)
            )
            rank = "bm25(search_index,3.0,0.15,1.0)"
        else:
            source, rank = "files f", "0.0"
            for word in tokens:
                where.append(
                    "(lower(f.name) LIKE ? ESCAPE '\\' OR lower(f.text) LIKE ? ESCAPE '\\')"
                )
                pattern = (
                    "%"
                    + word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                    + "%"
                )
                args.extend([pattern, pattern])
        if extension:
            where.append("f.extension=?")
            args.append("." + extension.lstrip(".").lower())
        if root is not None:
            where.append("f.root_id=?")
            args.append(root)
        # Fetch a bounded set before filtering JSON tags without relying on SQLite JSON1.
        cap = max(limit, 1000) if tag else limit
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        fields = "f.id,f.name,f.path,f.extension,f.size,f.method,f.warning,f.tags,f.indexed,f.text"
        rows = self.store.rows(
            f"SELECT {fields},{rank} AS rank FROM {source}{clause} "
            "ORDER BY rank ASC,f.name COLLATE NOCASE LIMIT ?",
            (*args, cap),
        )
        output = []
        for row in rows:
            row["tags"] = json.loads(row["tags"])
            if tag and tag not in row["tags"]:
                continue
            text = row.pop("text")
            matches = [
                m.start()
                for word in tokens
                for m in [re.search(re.escape(word), text, re.I)]
                if m
            ]
            offset = max(0, min(matches) - 60) if matches else 0
            row["snippet"] = text[offset : offset + 260]
            row["match_reason"] = (
                "Filename match"
                if any(t in row["name"].casefold() for t in tokens)
                else (
                    "Document text match"
                    if tokens and matches
                    else "Path or metadata match" if tokens else "Indexed file"
                )
            )
            row["text_length"] = len(text)
            output.append(row)
            if len(output) >= limit:
                break
        suggestions = []
        if not output and tokens and self.fts:
            vocab = [
                r["term"]
                for r in self.store.rows(
                    "SELECT term FROM search_vocabulary ORDER BY cnt DESC LIMIT 5000"
                )
            ]
            for token in tokens:
                suggestions.extend(
                    difflib.get_close_matches(token, vocab, n=3, cutoff=0.72)
                )
        return {
            "results": output,
            "suggestions": list(dict.fromkeys(suggestions)),
            "limit": limit,
            "limited": len(output) >= limit,
            "engine": "SQLite FTS5" if self.fts else "Plain text search",
        }

    def ranked_search(
        self,
        query: str = "",
        *,
        mode: str = "hybrid",
        extension: str = "",
        tag: str = "",
        root: int | None = None,
        limit: int = 100,
    ) -> dict:
        if mode not in {"keyword", "semantic", "hybrid"}:
            raise InputError("Choose keyword, semantic, or hybrid search.")
        if not query.strip() or mode == "keyword":
            return self.search(
                query, extension=extension, tag=tag, root=root, limit=limit
            )
        where, args = [], []
        if extension:
            where.append("extension=?")
            args.append("." + extension.lstrip(".").lower())
        if root is not None:
            where.append("root_id=?")
            args.append(root)
        clause = " WHERE " + " AND ".join(where) if where else ""
        records = self.store.rows(
            "SELECT id,name,path,extension,size,method,warning,tags,indexed,text FROM files"
            + clause
            + " ORDER BY id LIMIT 2001",
            tuple(args),
        )
        if len(records) > 2000:
            raise InputError(
                "Select a folder filter for semantic search across more than 2,000 files. Keyword search covers the full index."
            )
        for row in records:
            row["tags"] = json.loads(row["tags"])
        records = [r for r in records if not tag or tag in r["tags"]]
        ranked = self.semantic_cache.search(
            records,
            query,
            model_path=self.store.get("semantic_model_path", ""),
            limit=limit,
        )
        if mode == "semantic":
            return ranked
        keyword = self.search(
            query, extension=extension, tag=tag, root=root, limit=limit
        )
        fused, rows = {}, {}
        for result in [ranked, keyword]:
            for position, row in enumerate(result["results"]):
                ident = row["id"]
                fused[ident] = fused.get(ident, 0) + 1 / (60 + position + 1)
                rows[ident] = {**rows.get(ident, {}), **row}
        combined = [
            {**rows[ident], "fusion_score": round(fused[ident], 6)}
            for ident in sorted(fused, key=lambda ident: (-fused[ident], ident))[:limit]
        ]
        return {
            **ranked,
            "results": combined,
            "engine": "Keyword + " + ranked["engine"],
            "suggestions": keyword["suggestions"],
            "fusion": "Reciprocal rank fusion, k=60",
        }

    def preview(self, ident: int) -> dict:
        row = self.store.one("SELECT * FROM files WHERE id=?", (ident,))
        if not row:
            raise InputError("This file is not in the current index.")
        row["tags"] = json.loads(row["tags"])
        row["exists"] = Path(row["path"]).is_file()
        return row

    def duplicates(self) -> dict:
        groups = self.store.rows(
            "SELECT sha256,COUNT(*) AS count,MAX(size) AS size FROM files "
            "WHERE sha256<>'' GROUP BY sha256 HAVING COUNT(*)>1 ORDER BY MAX(size) DESC LIMIT 100"
        )
        for group in groups:
            group["files"] = self.store.rows(
                "SELECT id,name,path FROM files WHERE sha256=? ORDER BY path",
                (group["sha256"],),
            )
            group["extra_bytes"] = group["size"] * (group["count"] - 1)
        return {
            "groups": groups,
            "extra_bytes": sum(g["extra_bytes"] for g in groups),
            "note": "Equal SHA-256 hashes identify byte-identical indexed copies. No files are deleted.",
        }

    def similar(self, ident: int) -> dict:
        source = self.preview(ident)
        result = self.ranked_search(
            (source["name"] + " " + source["text"])[:4000], mode="semantic", limit=13
        )
        return {
            "results": [r for r in result["results"] if r["id"] != ident][:12],
            "method": result["engine"] + ". Similarity values are not probabilities.",
        }

    def word_similar(self, ident: int) -> dict:
        source = self.preview(ident)
        a = set(query_tokens_long(source["text"]))
        rows = self.store.rows(
            "SELECT id,name,path,text FROM files WHERE id<>? AND extension=? LIMIT 200",
            (ident, source["extension"]),
        )
        hits = []
        for row in rows:
            b = set(query_tokens_long(row.pop("text")))
            score = len(a & b) / len(a | b) if a | b else 0
            if score >= 0.08:
                hits.append({**row, "word_overlap": round(score, 3)})
        return {
            "results": sorted(hits, key=lambda r: -r["word_overlap"])[:12],
            "method": "Word-set overlap, not semantic or AI similarity. At most 200 same-type files are compared.",
        }


def query_tokens_long(text: str) -> list[str]:
    return re.findall(r"[^\W_]{3,}", text.casefold(), flags=re.UNICODE)[:6000]
