import sys
from pathlib import Path

# Ensure repo root is on the path so backend/ and ecb_pdf_to_json are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.main import app
from mangum import Mangum

# Vercel Python runtime looks for a callable named 'handler'
handler = Mangum(app, lifespan="off")
