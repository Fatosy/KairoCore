from KairoCore import run_kairo
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    run_kairo("example", 5040, "0.0.0.0")