"""
benchmark.py — Comprehensive Performance & Accuracy Benchmark for KinderSort.

Compares Baseline (Original Unoptimized System) vs New Local Hybrid AI Strategy.
Evaluates: Processing Speed, Memory (RAM Delta), Detection Recall, and Faces Found.
"""

import gc
import os
import time
from pathlib import Path

import face_recognition
import psutil


def run_benchmark(dataset_folder: str, ref_folder: str):
    """Executes benchmark and prints detailed metrics comparison."""
    dataset_path = Path(dataset_folder)
    ref_path = Path(ref_folder)

    # Collect images
    images = list(dataset_path.rglob("*.jpg")) + list(dataset_path.rglob("*.png"))
    ref_images = list(ref_path.glob("*.jpg")) + list(ref_path.glob("*.png"))

    if not images or not ref_images:
        print(f"[ERROR] Missing images. Checked: Events='{dataset_folder}', Reference='{ref_folder}'")
        return

    process = psutil.Process(os.getpid())
    print("==================================================")
    print(f"=== Starting KinderSort Benchmark ===")
    print(f"=== Test Photos      : {len(images)} images ===")
    print(f"=== Reference Students: {len(ref_images)} students ===")
    print("==================================================\n")

    # ----------------------------------------------------
    # TEST 1: Baseline (Unoptimized System)
    # ----------------------------------------------------
    gc.collect()
    print("[1/2] Running Baseline Strategy (Unoptimized)...")
    start_time = time.time()
    start_mem = process.memory_info().rss / (1024 * 1024)

    base_detected_photos = 0
    base_total_faces = 0

    for img in images:
        loaded = face_recognition.load_image_file(str(img))
        locs = face_recognition.face_locations(loaded, model="hog")
        encs = face_recognition.face_encodings(loaded, known_face_locations=locs, num_jitters=10, model="large")
        if encs:
            base_detected_photos += 1
            base_total_faces += len(encs)
        del loaded

    old_duration = time.time() - start_time
    old_mem = max(0.0, (process.memory_info().rss / (1024 * 1024)) - start_mem)

    # ----------------------------------------------------
    # TEST 2: New High-Accuracy Local AI Strategy
    # ----------------------------------------------------
    gc.collect()
    print("\n[2/2] Running New High-Accuracy Local AI Strategy...")
    start_time = time.time()
    start_mem = process.memory_info().rss / (1024 * 1024)

    from sorter import PhotoSorter
    sorter = PhotoSorter(ref_path, dataset_path, dataset_path, None)

    new_detected_photos = 0
    new_total_faces = 0

    for img in images:
        rgb_arr = sorter._load_and_enhance(img)
        locs, rgb_arr = sorter._detect_faces_pyramid(rgb_arr)
        encs = face_recognition.face_encodings(rgb_arr, locs, num_jitters=1, model="large")
        if encs:
            new_detected_photos += 1
            new_total_faces += len(encs)
        del rgb_arr

    new_duration = time.time() - start_time
    new_mem = max(0.0, (process.memory_info().rss / (1024 * 1024)) - start_mem)

    # ----------------------------------------------------
    # Metrics Comparison Summary
    # ----------------------------------------------------
    speedup = ((old_duration - new_duration) / old_duration) * 100 if old_duration > 0 else 0
    base_rate = (base_detected_photos / len(images)) * 100
    new_rate = (new_detected_photos / len(images)) * 100

    print("\n================ BENCHMARK RESULTS ================")
    print(f"1. Processing Speed:")
    print(f"   - Baseline Time  : {old_duration:.2f} s")
    print(f"   - New System Time: {new_duration:.2f} s")
    print(f"   - Efficiency Gain: {speedup:.1f}% faster⚡\n")

    print(f"2. Memory Usage (RAM Delta):")
    print(f"   - Baseline RAM   : {old_mem:.2f} MB")
    print(f"   - New System RAM : {new_mem:.2f} MB\n")

    print(f"3. AI Detection & Accuracy Metrics:")
    print(f"   - Baseline Photos Recognized  : {base_detected_photos}/{len(images)} ({base_rate:.1f}%)")
    print(f"   - New System Photos Recognized : {new_detected_photos}/{len(images)} ({new_rate:.1f}%)")
    print(f"   - Baseline Total Faces Found  : {base_total_faces}")
    print(f"   - New System Total Faces Found : {new_total_faces}")
    print("==================================================")


if __name__ == "__main__":
    run_benchmark("./Events", "./referencePhoto")