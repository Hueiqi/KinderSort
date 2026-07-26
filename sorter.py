"""
sorter.py — High-Precision Local AI Engine for KinderSort.

Key Engine Features:
- Preprocessing: CLAHE Adaptive Local Contrast & Edge Sharpening for difficult lighting.
- Multi-Scale Pyramid Detection: HOG Pyramid Upsampling to capture distant/small student faces.
- Low-Resource Processing: one image decoded at a time, released as soon as its
  encodings are extracted, so peak memory stays flat across a large event folder.
"""

import gc
import logging
from collections.abc import Callable
from pathlib import Path

import cv2
import face_recognition
import numpy as np
from PIL import UnidentifiedImageError

from utils import (
    build_output_filename,
    collect_event_images,
    is_image_file,
    safe_copy,
)


class PhotoSorter:
    """Ultra-High Accuracy Local AI Photo Sorter."""

    DISTANCE_THRESHOLD = 0.54
    """Max face distance to count as a match (lower = stricter; raise for more recall)."""

    MAX_IMAGE_DIMENSION = 1400
    """Optimal long-side limit for preserving small facial features while keeping CPU processing fast."""

    def __init__(
        self,
        reference_folder: Path,
        events_folder: Path,
        output_folder: Path,
        logger: logging.Logger | None = None,
    ) -> None:
        self.reference_folder = reference_folder
        self.events_folder = events_folder
        self.output_folder = output_folder
        self.logger = logger
        # Maps student name -> list of 128-D float32 face encodings
        self._student_encodings: dict[str, list[np.ndarray]] = {}
        # Same data pre-stacked into one array per student for fast matching
        self._stacked_encodings: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------
    # Local Preprocessing: CLAHE + Resizing + Sharpening
    # ------------------------------------------------------------------

    def _load_and_enhance(self, image_path: Path) -> np.ndarray:
        """Apply CLAHE local illumination enhancement and sharpening for dark/shadowed faces."""
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise UnidentifiedImageError(f"Cannot read image: {image_path}")

        h, w = img_bgr.shape[:2]
        longest = max(h, w)
        if longest > self.MAX_IMAGE_DIMENSION:
            scale = self.MAX_IMAGE_DIMENSION / longest
            img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)

        # LAB color space transformation for CLAHE
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)

        limg = cv2.merge((cl, a, b))
        enhanced_bgr = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

        # Mild sharpening filter
        kernel = np.array([[0, -0.5, 0], [-0.5, 3.0, -0.5], [0, -0.5, 0]])
        sharpened_bgr = cv2.filter2D(enhanced_bgr, -1, kernel)

        return cv2.cvtColor(sharpened_bgr, cv2.COLOR_BGR2RGB)

    # ------------------------------------------------------------------
    # Multi-Scale Pyramid Detection
    # ------------------------------------------------------------------

    def _detect_faces_pyramid(self, rgb_image: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Detect faces using multi-pass HOG pyramid upsampling.

        Returns a list of (top, right, bottom, left) boxes.  The image is not
        modified, so callers keep using the array they passed in.
        """
        # Pass 1: Standard HOG with upsampling
        boxes = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=1, model="hog")

        # Pass 2: Deeper upsampling for small/faraway student faces
        if not boxes:
            boxes = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=2, model="hog")

        return boxes

    @staticmethod
    def _box_area(box: tuple[int, int, int, int]) -> int:
        """Return the pixel area of a (top, right, bottom, left) face box."""
        top, right, bottom, left = box
        return (bottom - top) * (right - left)

    # ------------------------------------------------------------------
    # Reference Loading
    # ------------------------------------------------------------------

    def load_references(
        self,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[str]:
        """Load reference photos with jitter averaging for clean base vectors."""
        no_face_names: list[str] = []

        reference_images = sorted(
            p for p in self.reference_folder.iterdir() if is_image_file(p)
        )

        if not reference_images:
            if self.logger:
                self.logger.warning("No reference images found in %s", self.reference_folder)
            return no_face_names

        total = len(reference_images)
        for current, ref_path in enumerate(reference_images, start=1):
            student_name = ref_path.stem.split("_")[0]
            if progress_callback:
                progress_callback(current, total, student_name)

            rgb_image = None
            try:
                rgb_image = self._load_and_enhance(ref_path)
                locations = self._detect_faces_pyramid(rgb_image)

                if not locations:
                    if self.logger:
                        self.logger.warning("No face detected in reference photo for %s (%s)", student_name, ref_path.name)
                    no_face_names.append(student_name)
                    continue

                # A reference photo may catch a parent or sibling in frame.  HOG
                # returns boxes in no meaningful order, so take the largest face
                # rather than whichever happened to be found first.
                if len(locations) > 1 and self.logger:
                    self.logger.warning(
                        "%d faces found in reference photo %s — using the largest one for %s",
                        len(locations), ref_path.name, student_name,
                    )
                primary_face = max(locations, key=self._box_area)

                encodings = face_recognition.face_encodings(
                    rgb_image,
                    known_face_locations=[primary_face],
                    num_jitters=3,
                    model="large",
                )

                if not encodings:
                    if self.logger:
                        self.logger.warning("Could not encode face in reference photo for %s (%s)", student_name, ref_path.name)
                    no_face_names.append(student_name)
                    continue

                self._student_encodings.setdefault(student_name, []).append(encodings[0])
                if self.logger:
                    self.logger.info("Loaded reference vector for %s", student_name)

            except Exception as exc:  # noqa: BLE001
                if self.logger:
                    self.logger.error("Could not read reference photo %s: %s", ref_path.name, exc)
            finally:
                # Release the decoded image before the next reference is loaded.
                rgb_image = None

        # Pre-stack each student's vectors once so matching does no per-face
        # allocation later.
        self._stacked_encodings = {
            name: np.stack(vectors) for name, vectors in self._student_encodings.items()
        }
        gc.collect()

        # A student with several reference photos may have failed on one and
        # succeeded on another — don't warn the teacher about those.
        return [name for name in dict.fromkeys(no_face_names) if name not in self._student_encodings]

    # ------------------------------------------------------------------
    # Main Sorting Pipeline
    # ------------------------------------------------------------------

    def sort_all(
        self,
        progress_callback: Callable[[int, int, str], None],
        cancelled: Callable[[], bool],
    ) -> dict[str, int]:
        """Process event images locally."""
        images = collect_event_images(self.events_folder)
        total = len(images)
        counts = {"total": total, "matched": 0, "unmatched": 0, "skipped": 0}

        if self.logger:
            self.logger.info("Starting High-Accuracy AI sort — %d images found", total)

        for current, (image_path, event_name) in enumerate(images, start=1):
            if cancelled():
                if self.logger:
                    self.logger.info("Sort cancelled by user at image %d/%d", current, total)
                break

            progress_callback(current, total, image_path.name)
            output_filename = build_output_filename(event_name, image_path.name)
            rgb_image = None

            try:
                rgb_image = self._load_and_enhance(image_path)
            except UnidentifiedImageError:
                safe_copy(image_path, self.output_folder / "_unmatched", output_filename, self.logger)
                counts["unmatched"] += 1
                continue
            except Exception as exc:  # noqa: BLE001
                if self.logger:
                    self.logger.error("Could not open %s: %s — skipping", image_path.name, exc)
                # Still preserve the photo so nothing silently disappears.
                safe_copy(image_path, self.output_folder / "_unmatched", output_filename, self.logger)
                counts["skipped"] += 1
                continue

            try:
                face_locations = self._detect_faces_pyramid(rgb_image)
                face_encodings = face_recognition.face_encodings(
                    rgb_image, face_locations, num_jitters=1, model="large"
                )

            except Exception as exc:  # noqa: BLE001
                if self.logger:
                    self.logger.error("Face detection failed for %s: %s", image_path.name, exc)
                safe_copy(image_path, self.output_folder / "_unmatched", output_filename, self.logger)
                counts["unmatched"] += 1
                continue
            finally:
                # Drop the decoded image now that the encodings are extracted —
                # it is the largest object in the loop and is not needed to copy.
                rgb_image = None

            if not face_encodings:
                if self.logger:
                    self.logger.info("No face detected: %s → _unmatched", image_path.name)
                safe_copy(image_path, self.output_folder / "_unmatched", output_filename, self.logger)
                counts["unmatched"] += 1
                continue

            matched_students: set[str] = set()
            for encoding in face_encodings:
                match = self._match_face(encoding)
                if match:
                    matched_students.add(match)

            if matched_students:
                for student_name in matched_students:
                    dest_folder = self.output_folder / student_name
                    safe_copy(image_path, dest_folder, output_filename, self.logger)
                    if self.logger:
                        self.logger.info("Matched %s → %s", image_path.name, student_name)
                counts["matched"] += 1
            else:
                if self.logger:
                    self.logger.info("No student match: %s → _unmatched", image_path.name)
                safe_copy(image_path, self.output_folder / "_unmatched", output_filename, self.logger)
                counts["unmatched"] += 1

        if self.logger:
            self.logger.info(
                "Sort complete — total=%d matched=%d unmatched=%d skipped=%d",
                counts["total"], counts["matched"], counts["unmatched"], counts["skipped"]
            )
        return counts

    # ------------------------------------------------------------------
    # Vector Comparison Optimization
    # ------------------------------------------------------------------

    def _match_face(self, encoding: np.ndarray) -> str | None:
        """Return the closest student within DISTANCE_THRESHOLD, or None.

        Compares the given encoding against every stored reference vector and
        picks the student with the smallest Euclidean distance.
        """
        if not self._stacked_encodings:
            return None

        best_match_student = None
        min_distance = float("inf")

        for student_name, known_encodings in self._stacked_encodings.items():
            distances = face_recognition.face_distance(known_encodings, encoding)
            student_min_dist = float(np.min(distances))

            if student_min_dist < min_distance:
                min_distance = student_min_dist
                best_match_student = student_name

        if min_distance <= self.DISTANCE_THRESHOLD:
            return best_match_student

        return None
