import argparse

from app.main import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate fictional document images.")
    parser.parse_args()
    raise SystemExit(main(interactive=True))