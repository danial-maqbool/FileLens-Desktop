"""Incremental search correctness, filters, ownership, and duplicate evidence."""
import json
from app.indexer import query_tokens
from localdesk.safety import InputError, digest
from tests.support import AppCase, Context

class IndexTests(AppCase):
    def seed(self):
        self.file('notes.txt','inventory review and local search')
        self.file('copy.txt','inventory review and local search')
        self.file('other.md','transformer attention study')
        root=self.app.index.add_root(str(self.workspace))
        result=self.app.index.scan(root['id'],Context());return root,result
    def test_first_scan_indexes_all_files(self):
        root,r=self.seed();self.assertEqual(len(self.app.index.search()['results']),3)
    def test_keyword_search_has_real_snippets(self):
        self.seed();r=self.app.index.search('inventory');self.assertEqual(len(r['results']),2)
        self.assertIn('inventory',r['results'][0]['snippet'])
    def test_prefix_search(self):
        self.seed();self.assertEqual(len(self.app.index.search('transf')['results']),1)
    def test_query_operators_cannot_inject_sql(self):
        self.seed();self.app.index.search('" OR 1=1 -- <script>')
        self.assertEqual(len(self.app.index.search()['results']),3)
    def test_query_token_limit(self):self.assertEqual(len(query_tokens('word '*30)),20)
    def test_extension_filter(self):
        self.seed();r=self.app.index.search(extension='md');self.assertEqual(len(r['results']),1)
    def test_duplicate_hash_groups(self):
        self.seed();r=self.app.index.duplicates();self.assertEqual(len(r['groups']),1)
        self.assertEqual(r['groups'][0]['count'],2);self.assertGreater(r['extra_bytes'],0)
    def test_second_scan_skips_unchanged_files(self):
        root,_=self.seed();r=self.app.index.scan(root['id'],Context());self.assertEqual(r['unchanged'],3)
    def test_changed_file_replaces_old_search_text(self):
        root,_=self.seed();self.file('other.md','replaced document')
        self.app.index.scan(root['id'],Context());self.assertEqual(self.app.index.search('transformer')['results'],[])
        self.assertEqual(len(self.app.index.search('replaced')['results']),1)
    def test_deleted_file_is_removed_from_index(self):
        root,_=self.seed();(self.workspace/'other.md').unlink();self.app.index.scan(root['id'],Context())
        self.assertEqual(self.app.index.search('transformer')['results'],[])
    def test_remove_root_does_not_delete_sources(self):
        root,_=self.seed();p=self.workspace/'notes.txt';h=digest(p)
        self.app.index.remove_root(root['id']);self.assertEqual(self.app.index.search()['results'],[]);self.assertEqual(digest(p),h)
    def test_overlapping_roots_are_rejected(self):
        self.seed();child=self.workspace/'child';child.mkdir()
        with self.assertRaises(InputError):self.app.index.add_root(str(child))
    def test_private_data_cannot_be_indexed(self):
        with self.assertRaises(InputError):self.app.index.add_root(str(self.app.data))
    def test_preview_contains_indexed_text(self):
        self.seed();hit=self.app.index.search('transformer')['results'][0]
        preview=self.app.index.preview(hit['id']);self.assertIn('attention',preview['text']);self.assertTrue(preview['exists'])
    def test_tag_filter(self):
        self.seed();hit=self.app.index.search('transformer')['results'][0]
        self.app.post('tags',{'id':hit['id'],'tags':['course','course']})
        self.assertEqual(len(self.app.index.search(tag='course')['results']),1)
    def test_search_export_respects_root(self):
        root,_=self.seed();outside=self.base/'outside';outside.mkdir();(outside/'another.txt').write_text('inventory')
        second=self.app.index.add_root(str(outside));self.app.index.scan(second['id'],Context())
        a=self.app.post('export',{'query':'inventory','root':second['id'],'format':'json'})
        result=json.loads(self.output(a));self.assertEqual(len(result['results']),1);self.assertEqual(result['results'][0]['name'],'another.txt')
    def test_plain_search_fallback(self):
        self.seed();self.app.index.fts=False
        self.assertEqual(len(self.app.index.search('inventory')['results']),2)
    def test_similar_files_use_local_model(self):
        self.seed();hit=self.app.index.search('inventory')['results'][0]
        r=self.app.index.similar(hit['id']);self.assertEqual(r['results'][0]['semantic_score'],1.0)
        self.assertIn('not probabilities',r['method'])
    def test_auto_rescan_is_off_on_startup(self):self.assertFalse(self.app.state()['watcher']['enabled'])
    def test_unsupported_file_has_coverage_warning(self):
        self.file('unknown.bin',b'\x00\x01');root=self.app.index.add_root(str(self.workspace));self.app.index.scan(root['id'],Context())
        r=self.app.index.search()['results'];self.assertEqual(len(r),1);self.assertTrue(r[0]['warning'])
