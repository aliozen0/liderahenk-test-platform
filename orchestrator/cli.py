#!/usr/bin/env python3
"""
LiderAhenk Test Senaryo Motoru — CLI Arayüzü
─────────────────────────────────────────────
Kullanım:
  python3 orchestrator/cli.py --scenario orchestrator/scenarios/basic_task.yml
  python3 orchestrator/cli.py --list
"""

import argparse
import sys
import os
from pathlib import Path

# Proje kökünü sys.path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.main import ScenarioRunner


def main():
    parser = argparse.ArgumentParser(
        description="LiderAhenk Test Senaryo Motoru")
    parser.add_argument("--scenario", help="Senaryo YAML dosyası")
    parser.add_argument("--list", action="store_true",
                        help="Mevcut senaryoları listele")
    args = parser.parse_args()

    if args.list:
        scenario_dir = Path("orchestrator/scenarios")
        if not scenario_dir.exists():
            print("Senaryo dizini bulunamadı: orchestrator/scenarios/")
            sys.exit(1)
        scenarios = sorted(scenario_dir.glob("*.yml"))
        print("\nMevcut senaryolar:")
        for s in scenarios:
            print(f"  - {s.name}")
        print(f"\nToplam: {len(scenarios)} senaryo")
        return

    if not args.scenario:
        parser.print_help()
        sys.exit(1)

    scenario_path = args.scenario
    if not Path(scenario_path).exists():
        print(f"Dosya bulunamadı: {scenario_path}")
        sys.exit(1)

    runner = ScenarioRunner()
    results = runner.run(scenario_path)
    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
