"""Slot reading must work in every HUD color: no filled slot may be missed; stack numbers must read right."""
import pytest

from ntc import detect, slots

from conftest import (INVENTORY_NON_TECH, CABINET_FILLED, CABINET_STACKS, INVENTORY_FILLED, INVENTORY_STACKS, OPTIONS_OVER_HUD,
                      load_theme, needs_tesseract, theme_ids)


def windows(tid):
    return {w.kind: w for w in detect.find_windows(load_theme(tid))}


def cases():
    for tid in theme_ids():
        if tid == "14":
            continue
        yield tid, "cabinet", CABINET_FILLED, CABINET_STACKS
        if tid != "05":
            yield tid, "inventory", INVENTORY_FILLED, INVENTORY_STACKS


@pytest.mark.parametrize("tid,kind,filled,stacks", list(cases()))
def test_no_filled_slot_is_missed(tid, kind, filled, stacks):
    img, w = load_theme(tid), windows(tid)[kind]
    cand = {(s.row, s.col) for s in slots.analyze(img, w) if s.candidate}
    assert filled <= cand, f"missed {sorted(filled - cand)}"


def test_candidates_are_not_wildly_over_inclusive():
    """Extra candidates are cleared by the hover (no tooltip on an empty slot), but they cost scan time."""
    extra = total = 0
    for tid, kind, filled, _ in cases():
        img, w = load_theme(tid), windows(tid)[kind]
        for s in slots.analyze(img, w):
            if (s.row, s.col) not in filled:
                total += 1
                extra += s.candidate
    assert extra / total < 0.15


@needs_tesseract
def test_stack_numbers_read_correctly_in_every_theme(cfg):
    ok = bad = phantom = tests = 0
    misses = []
    for tid, kind, filled, stacks in cases():
        if tid in OPTIONS_OVER_HUD:
            continue                                  # these captures have the Options window over parts of the HUD
        img, w = load_theme(tid), windows(tid)[kind]
        plain = sorted(filled - set(stacks))[:8]              # a sample of slots that carry no number
        for (r, c) in sorted(set(stacks)) + plain:
            qty, flags = slots.read_qty(img, w.slot_rect(r, c))
            if (r, c) in stacks:
                if qty == stacks[(r, c)]:
                    ok += 1
                else:
                    bad += 1
                    misses.append((tid, kind, r, c, stacks[(r, c)], qty))
            else:
                tests += 1
                phantom += qty != 1
    assert phantom == 0, "a slot without a number must read as 1"
    assert ok / (ok + bad) >= 0.97, misses


def test_label_rule_skips_only_clear_non_techs():
    for text in ("ULT", "PIST", "SHLD"):
        assert slots.label_is_not_tech(text), text
    assert slots.label_is_not_tech("WLI") and not slots.label_is_not_tech("AIP") and not slots.label_is_not_tech("LUMP")
    for text in ("COMP", "HULL", "ATP", "CORE", "FRAM", "TECH", "AIP", "LUMP", "HRAM", "CRE", "COM", "PRA",
                 "AP", "II", "A", "L C", "", None):
        assert not slots.label_is_not_tech(text), text


@needs_tesseract
def test_labels_never_skip_a_tech_in_any_theme():
    """In all 13 usable HUD colors, no tech slot reads as a non-tech label; the ULT items do."""
    techs = skipped_techs = ult = 0
    for tid, kind, filled, _ in cases():
        img, w = load_theme(tid), windows(tid)[kind]
        for (r, c) in sorted(filled):
            if kind == "inventory" and (r, c) in INVENTORY_NON_TECH:
                ult += slots.label_is_not_tech(slots.read_label(img, w.slot_rect(r, c)))
            elif kind == "inventory" and c == 7 or kind == "inventory" and (r, c) == (5, 6):
                continue                                  # partly covered / unclear in the captures
            else:
                techs += 1
                skipped_techs += slots.label_is_not_tech(slots.read_label(img, w.slot_rect(r, c)))
    assert skipped_techs == 0 and techs > 500
    assert ult >= 0.9 * 4 * 12
