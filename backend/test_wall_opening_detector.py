#!/usr/bin/env python3
"""
Test script for production door detection.

Tests the YOLO-primary hybrid detection against:
1. TES_5AH_PGT_G_B-1_W2_000_-KA.pdf - Basement level, ~35 doors expected
2. TES_5AH_PGT_G_H42_W2_001_-FA.pdf - Floor 42, exactly 6 doors expected
"""

import sys
import os
import time

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.wall_opening_detector import (
    detect_doors_yolo_primary,
    detect_doors_from_wall_openings,
    DoorDetectionResult,
)


def test_blueprint(pdf_path: str, expected_doors: int, scale: int = 100, name: str = "", dpi: int = 150):
    """Test door detection on a single blueprint."""
    print(f"\n{'='*60}")
    print(f"Testing: {name or pdf_path}")
    print(f"Expected doors: {expected_doors}")
    print(f"Scale: 1:{scale}, DPI: {dpi}")
    print(f"{'='*60}")

    if not os.path.exists(pdf_path):
        print(f"ERROR: File not found: {pdf_path}")
        return None

    try:
        # Use YOLO-primary detection (production recommended)
        result = detect_doors_yolo_primary(
            pdf_path=pdf_path,
            page_number=1,
            scale=scale,
            dpi=dpi,
            confidence_threshold=0.3,
            use_wall_opening_validation=False,  # YOLO is sufficient
        )

        print(f"\nResults:")
        print(f"  Doors detected: {len(result.doors)}")
        print(f"  Expected: {expected_doors}")
        print(f"  Accuracy: {abs(len(result.doors) - expected_doors) / expected_doors * 100:.1f}% deviation")
        print(f"  Total openings analyzed: {result.total_openings_analyzed}")
        print(f"  Hatch regions filtered: {result.hatch_regions_filtered}")
        print(f"  Processing time: {result.processing_time_ms}ms")

        if result.warnings:
            print(f"  Warnings: {result.warnings}")

        # Group by width
        by_width = result.to_dict()["by_width"]
        if by_width:
            print(f"\n  By width:")
            for width, count in sorted(by_width.items()):
                print(f"    {width}m: {count} doors")

        # Door type breakdown
        door_types = {}
        for door in result.doors:
            door_type = door.metadata.get("door_type", "unknown")
            door_types[door_type] = door_types.get(door_type, 0) + 1

        if door_types:
            print(f"\n  By type:")
            for dtype, count in door_types.items():
                print(f"    {dtype}: {count}")

        return result

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("Wall Opening Door Detector - Test Suite")
    print("=" * 60)

    # Test blueprints
    # Note: DPI 150 is recommended for YOLO (trained on this resolution)
    blueprints = [
        {
            "path": "/Volumes/SSK Drive/omniturm /01_Grundrisse/TES_5AH_PGT_G_H42_W2_001_-FA.pdf",
            "expected": 6,
            "scale": 50,  # Floor 42 is likely 1:50
            "dpi": 150,   # Standard YOLO resolution
            "name": "Floor 42 (H42) - 6 doors expected",
        },
        {
            "path": "/Volumes/SSK Drive/omniturm /01_Grundrisse/TES_5AH_PGT_G_B-1_W2_000_-KA.pdf",
            "expected": 35,
            "scale": 100,  # Basement is likely 1:100
            "dpi": 150,   # Standard YOLO resolution
            "name": "Basement B-1 - ~35 doors expected",
        },
    ]

    results = []
    for bp in blueprints:
        result = test_blueprint(
            bp["path"],
            bp["expected"],
            bp["scale"],
            bp["name"],
            bp.get("dpi", 150),
        )
        results.append({
            "name": bp["name"],
            "expected": bp["expected"],
            "detected": len(result.doors) if result else 0,
            "success": result is not None,
        })

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        status = "✓" if r["success"] else "✗"
        deviation = abs(r["detected"] - r["expected"])
        print(f"{status} {r['name']}: {r['detected']}/{r['expected']} (off by {deviation})")


if __name__ == "__main__":
    main()
