"""Seed script: no-op for Briefkasten (users register themselves)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def seed():
    print("Briefkasten: No seed data needed (users register via UI).")


if __name__ == "__main__":
    seed()
