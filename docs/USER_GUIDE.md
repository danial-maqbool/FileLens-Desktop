# Use FileLens

## Start

Run the setup commands in the README. Start with `start.bat --demo` or `sh start.sh --demo`. Select **Load demo folder**. Search for `attention`. Open a result and read its extraction notes.

## Add a folder

Open **Indexed folders**. Add a local folder. Select OCR only when you need image or scanned-PDF text. Start an index job. A folder is not scanned or watched until you request it. Keep default private-folder exclusions unless a specific task requires a change.

## Search

Use **Keyword** for exact terms. Use **Semantic** for local corpus similarity. Use **Hybrid** to combine both rankings. Scores are similarity measures, not confidence percentages. Small corpora use TF-IDF when latent semantic analysis is not useful.

The optional neural backend accepts a trusted local Sentence Transformers directory with safetensors weights. Install `requirements-neural.txt` first. Do not select model folders from unknown sources. The app does not download weights.

## Review and export

Select a result to read extracted text. Add up to 20 tags. Save recurring searches. Export filtered results as JSON or CSV. Review duplicate hashes before acting on source files. FileLens does not delete duplicate source files.

## Keep the index current

Run a normal rescan after editing files. Use a forced scan when content changed without a size or modification-time change. Enable interval rescans explicitly. Saved rescan settings resume after vault unlock. Install a user-login worker as described in `BACKGROUND.md` to keep the process independent from a terminal.
