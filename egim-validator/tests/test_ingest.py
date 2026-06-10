import json
import tempfile
import unittest
from pathlib import Path

from egim_validator.ingest import load_guide, load_model_doc, render_model_doc

SAMPLES = Path(__file__).resolve().parents[1] / "sample_data"


class TestIngest(unittest.TestCase):
    def test_load_sample_guide(self):
        paragraphs = load_guide(SAMPLES / "guide_paragraphs.sample.json")
        self.assertEqual(len(paragraphs), 6)
        self.assertEqual(paragraphs[0].ref, "EGIM-0001")
        self.assertIn("General topics", paragraphs[1].chapter)

    def test_load_sample_model_doc_json(self):
        doc = load_model_doc(SAMPLES / "model_doc.sample.json")
        self.assertEqual(len(doc.sections), 4)
        self.assertIn("GOV-1", doc.section_by_id())

    def test_markdown_split(self):
        md = "intro text\n\n# Governance\ngov body\n\n## Validation\nval body\n"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(md)
        doc = load_model_doc(f.name)
        headings = [s.heading for s in doc.sections]
        self.assertEqual(headings, ["Preamble", "Governance", "Validation"])
        self.assertEqual(doc.sections[2].text, "val body")

    def test_render_contains_section_ids(self):
        doc = load_model_doc(SAMPLES / "model_doc.sample.json")
        rendered = render_model_doc(doc)
        self.assertIn('<section id="GOV-1"', rendered)
        self.assertTrue(rendered.startswith("<model_documentation"))

    def test_json_list_form(self):
        data = [{"id": "A", "heading": "H", "text": "T"}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
        doc = load_model_doc(f.name)
        self.assertEqual(doc.sections[0].id, "A")


if __name__ == "__main__":
    unittest.main()
