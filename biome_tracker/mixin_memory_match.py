import time
import cv2
import numpy as np
from PIL import ImageGrab


class MemoryMatchMixin:
    """
    Automated Memory Match solver:
    - Fixed 5x4 grid (20 cells, index range 0..19).
    - Limit: 10 attempts.
    - Pure image hashing (dHash) on entire cell (icon + multiplier count).
    - Remembers all flipped cards to auto-complete pairs on discovery.
    - Strictly English logging.
    """

    def _dhash(self, image, hash_size=16):
        resized = cv2.resize(image, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        return sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])

    def _hash_similarity(self, h1, h2, threshold=8):
        if h1 is None or h2 is None:
            return False
        return bin(h1 ^ h2).count('1') <= threshold

    def _capture_cell(self, center_x, center_y, cell_w, cell_h):
        x1 = int(center_x - cell_w // 2)
        y1 = int(center_y - cell_h // 2)
        x2 = int(center_x + cell_w // 2)
        y2 = int(center_y + cell_h // 2)

        screen = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        return cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)

    def _scan_cell(self, cell_idx):
        coords = self.config.get("memory_match_cells", [])
        if cell_idx >= len(coords):
            return None

        cx, cy = coords[cell_idx]
        cw = self.config.get("memory_match_cell_width", 76)
        ch = self.config.get("memory_match_cell_height", 76)

        cell_img = self._capture_cell(cx, cy, cw, ch)

        # Crop outer card borders (10%), captures central icon + bottom count label
        h, w, _ = cell_img.shape
        inner_roi = cell_img[int(h * 0.10):int(h * 0.95), int(w * 0.10):int(w * 0.90)]
        gray = cv2.cvtColor(inner_roi, cv2.COLOR_BGR2GRAY)

        return self._dhash(gray)

    def _click_cell(self, cell_idx):
        coords = self.config.get("memory_match_cells", [])
        if cell_idx < len(coords):
            cx, cy = coords[cell_idx]
            self.click(cx, cy)

    def run_memory_match(self):
        self.logger.info("[Memory Match] Starting solver (5x4 grid, 20 cells, 10 attempts max)...")
        time.sleep(self.config.get("memory_match_start_delay", 1.0))

        board = {}            # {cell_idx: hash}
        matched_cells = set() # Set of already solved cells
        attempts_left = 10

        def find_match_in_memory(target_idx, target_hash):
            for idx, h in board.items():
                if idx != target_idx and idx not in matched_cells:
                    if self._hash_similarity(h, target_hash):
                        return idx
            return None

        def find_known_pair():
            unmatched = [i for i in board if i not in matched_cells]
            for i in range(len(unmatched)):
                idx1 = unmatched[i]
                for j in range(i + 1, len(unmatched)):
                    idx2 = unmatched[j]
                    if self._hash_similarity(board[idx1], board[idx2]):
                        return idx1, idx2
            return None

        while attempts_left > 0 and len(matched_cells) < 20:
            # 1. Check if both cards of an identical pair are already known in memory
            pair = find_known_pair()
            if pair:
                c1, c2 = pair
                self.logger.info(f"[Memory Match] Matching known pair from memory: cells {c1} & {c2}")
                self._click_cell(c1)
                time.sleep(0.3)
                self._click_cell(c2)
                matched_cells.add(c1)
                matched_cells.add(c2)
                attempts_left -= 1
                time.sleep(1.0)
                continue

            # 2. Pick the first unopened unknown cell
            unopened = [i for i in range(20) if i not in board and i not in matched_cells]
            if not unopened:
                unopened = [i for i in range(20) if i not in matched_cells]
                if not unopened:
                    break

            first_cell = unopened[0]
            self._click_cell(first_cell)
            time.sleep(0.5)

            h1 = self._scan_cell(first_cell)
            board[first_cell] = h1

            # 3. Check if first flipped cell matches any previously discovered card
            matched_prev = find_match_in_memory(first_cell, h1)
            if matched_prev is not None:
                self.logger.info(f"[Memory Match] Cell {first_cell} matches previously seen cell {matched_prev}")
                self._click_cell(matched_prev)
                matched_cells.add(first_cell)
                matched_cells.add(matched_prev)
                attempts_left -= 1
                time.sleep(1.0)
                continue

            # 4. If no previous match, flip a second unknown cell
            candidates = [i for i in unopened if i != first_cell]
            if not candidates:
                candidates = [i for i in range(20) if i != first_cell and i not in matched_cells]

            second_cell = candidates[0]
            self._click_cell(second_cell)
            time.sleep(0.5)

            h2 = self._scan_cell(second_cell)
            board[second_cell] = h2
            attempts_left -= 1

            if self._hash_similarity(h1, h2):
                self.logger.info(f"[Memory Match] Instant pair match: cells {first_cell} & {second_cell}")
                matched_cells.add(first_cell)
                matched_cells.add(second_cell)
                time.sleep(1.0)
            else:
                self.logger.info(f"[Memory Match] No match: cells {first_cell} & {second_cell}. Waiting for flip back...")
                time.sleep(1.4)

        self.logger.info("[Memory Match] Attempts finished. Waiting for full board reveal...")
        time.sleep(self.config.get("memory_match_reveal_delay", 3.0))

        close_x = self.config.get("memory_match_close_x")
        close_y = self.config.get("memory_match_close_y")
        if close_x and close_y:
            self.click(close_x, close_y)
            self.logger.info("[Memory Match] Clicked Close button.")
