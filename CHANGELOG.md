# Changes

## 0.2.0

- Text and file search: Index selected folders. Search names, text, file types, and tags.
- Local OCR: Read images and scanned PDF pages with Tesseract. Record extraction notes.
- Semantic search: Fit a local latent semantic analysis model on indexed text. Combine it with keyword ranking.
- Local neural model: Select an existing trusted Sentence Transformers folder. No model download happens at runtime.
- Duplicate review: Group identical content hashes. Show related text without deleting source files.
- Persistent rescan: Resume explicitly enabled rescan settings after vault unlock. Install a user-login worker.
- Encrypted index: Store document text, tags, and job records in an AES-256-GCM vault.
- Reusable results: Export filtered JSON or CSV results and save searches.

The release also includes encrypted storage, request checks, portable output paths, synthetic examples, test reports, and recorded interface media.
