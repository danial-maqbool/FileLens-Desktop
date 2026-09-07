"""Local search API and user-controlled folder rescans."""
from __future__ import annotations
import csv
import io
import json
import threading
from pathlib import Path
from localdesk.base import BaseApplication
from localdesk.safety import InputError, integer, unique_write
from .indexer import Index


class Application(BaseApplication):
    def setup(self):
        self.index = Index(self.store, self.data)
        self.scan_lock = threading.Lock()
        self.watch_stop = threading.Event()
        self.watch_thread = None
        self.watcher = {'enabled': False, 'seconds': 60, 'last_error': ''}

    def state(self):
        stats = self.store.one('SELECT COUNT(*) AS files,COALESCE(SUM(size),0) AS bytes,'
                              "COALESCE(SUM(CASE WHEN text<>'' THEN 1 ELSE 0 END),0) AS searchable,"
                              "COALESCE(SUM(CASE WHEN warning<>'' THEN 1 ELSE 0 END),0) AS warnings FROM files")
        extensions = self.store.rows('SELECT extension,COUNT(*) AS count FROM files GROUP BY extension ORDER BY count DESC')
        return {'stats': stats, 'roots': self.store.rows('SELECT * FROM roots ORDER BY name'),
                'extensions': extensions, 'saved': self.store.rows('SELECT * FROM saved_searches ORDER BY name'),
                'semantic_model_path': self.store.get('semantic_model_path', ''), 'watcher': dict(self.watcher), 'jobs': self.jobs.recent(), 'fts5': self.index.fts}

    def scan(self, ident: int, force: bool = False):
        def work(context):
            with self.scan_lock:
                return self.index.scan(ident, context, force=force)
        return self.jobs.submit('Index folder', work)

    def get(self, action, query):
        if action == 'search':
            root = integer(query['root'], 1, 10**9) if query.get('root') else None
            return self.index.ranked_search(str(query.get('q', ''))[:500], mode=query.get('mode', 'keyword'), extension=query.get('extension', ''),
                                     tag=query.get('tag', ''), root=root,
                                     limit=integer(query.get('limit', 100), 1, 1000))
        if action == 'preview':
            return self.index.preview(integer(query.get('id'), 1, 10**12))
        if action == 'duplicates':
            return self.index.duplicates()
        if action == 'similar':
            return self.index.similar(integer(query.get('id'), 1, 10**12))
        return super().get(action, query)

    def stop_watch(self):
        self.watch_stop.set()
        if self.watch_thread:
            self.watch_thread.join(timeout=3)
        self.watcher['enabled'] = False

    def post(self, action, body):
        if action == 'semantic/model':
            path = str(body.get('path', '')).strip()
            if path:
                from localdesk.safety import checked_path
                checked_path(path, directory=True)
            self.store.set('semantic_model_path', path)
            self.index.semantic_cache.fingerprint = ''
            return {'saved': True, 'model': 'Local neural weights' if path else 'Local latent semantic analysis'}
        if action == 'roots/add':
            return self.index.add_root(body.get('path', ''), body.get('patterns'), bool(body.get('ocr', False)))
        if action == 'roots/remove':
            with self.scan_lock:
                self.index.remove_root(integer(body.get('id'), 1, 10**9))
            return {'removed': True, 'source_files_changed': False}
        if action == 'scan':
            return {'job_id': self.scan(integer(body.get('id'), 1, 10**9), bool(body.get('force', False)))}
        if action == 'tags':
            ident = integer(body.get('id'), 1, 10**12)
            self.index.preview(ident)
            tags = body.get('tags', [])
            if isinstance(tags, str):
                tags = tags.split(',')
            if not isinstance(tags, list) or len(tags) > 20:
                raise InputError('Use at most 20 tags per file.')
            tags = sorted(set(str(t).strip()[:40] for t in tags if str(t).strip()))
            self.store.execute('UPDATE files SET tags=? WHERE id=?', (json.dumps(tags), ident))
            return {'tags': tags}
        if action == 'saved/add':
            name = str(body.get('name', '')).strip()[:80]
            if not name:
                raise InputError('Enter a name for this saved search.')
            self.store.execute('INSERT INTO saved_searches(name,query,extension,tag) VALUES(?,?,?,?) '
                               'ON CONFLICT(name) DO UPDATE SET query=excluded.query,extension=excluded.extension,tag=excluded.tag',
                               (name, str(body.get('query', ''))[:500], str(body.get('extension', ''))[:20], str(body.get('tag', ''))[:40]))
            return {'saved': True}
        if action == 'saved/delete':
            self.store.execute('DELETE FROM saved_searches WHERE id=?', (integer(body.get('id'), 1, 10**9),))
            return {'deleted': True}
        if action == 'export':
            result = self.index.ranked_search(str(body.get('query', ''))[:500], mode=str(body.get('mode', 'keyword')),
                                       extension=str(body.get('extension', '')), tag=str(body.get('tag', '')), root=integer(body['root'], 1, 10**9) if body.get('root') else None, limit=1000)
            folder = self.new_output('search')
            if body.get('format', 'json') == 'csv':
                stream = io.StringIO(newline='')
                writer = csv.writer(stream)
                writer.writerow(['Name', 'Path', 'Bytes', 'Method', 'Tags', 'Coverage note'])
                for r in result['results']:
                    values = [r['name'], r['path'], str(r['size']), r['method'], ', '.join(r['tags']), r['warning']]
                    writer.writerow(["'" + v if v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
                path = unique_write(folder / 'search-results.csv', stream.getvalue().encode('utf-8-sig'))
            else:
                path = unique_write(folder / 'search-results.json', json.dumps(result, indent=2, ensure_ascii=False).encode('utf-8'))
            return self.artifact(path)
        if action == 'watch/start':
            self.stop_watch()
            if self.watch_thread and self.watch_thread.is_alive():
                raise InputError('The previous rescan service is still stopping.')
            seconds = integer(body.get('seconds', 60), 15, 86400)
            self.watch_stop = threading.Event()
            self.watcher = {'enabled': True, 'seconds': seconds, 'last_error': ''}
            def loop():
                while not self.watch_stop.wait(seconds) and not self.shutdown.is_set():
                    try:
                        active = self.store.one("SELECT COUNT(*) AS n FROM jobs WHERE status IN ('running','queued')")['n']
                        if not active:
                            for r in self.store.rows('SELECT id FROM roots LIMIT 8'):
                                self.scan(r['id'])
                        self.watcher['last_error'] = ''
                    except Exception as exc:
                        self.watcher['last_error'] = str(exc)[:250]
                self.watcher['enabled'] = False
            self.watch_thread = threading.Thread(target=loop, daemon=True, name='file-index-rescan')
            self.watch_thread.start()
            return self.watcher
        if action == 'watch/stop':
            self.stop_watch()
            return self.watcher
        return super().post(action, body)

    def close(self):
        self.stop_watch()
        super().close()
