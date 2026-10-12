"""
sputum_control.py — DNA extraction sequence for Sputum samples.

Relies on sequence_helpers for stop/pause-aware primitives so each
step is one readable line instead of four.
"""

from sequence_helpers import run_sequence, check, move, move_both, wait, mix


def _sputum_steps():
    # ── LYSIS ──────────────────────────────────────────────────
    move(2257, 3, 0.0004, 'right')
    wait(0.5)
    move(850, 2, 0.0004, 'down')
    wait(0.5)
    mix(2, 1200, mode='normal', timer=True)     # 20 min lysis
    wait(0.5)
    move(850, 2, 0.0004, 'up')
    wait(0.5)

    # ── BEAD COLLECTING ────────────────────────────────────────
    move(450, 3, 0.0004, 'right')
    wait(0.5)
    move_both(1700, 1, 2, 0.0002, 'down');   wait(30, timer=True)
    move_both(1700, 1, 2, 0.0002, 'up');     wait(0.5)

    # ── BEAD BINDING ───────────────────────────────────────────
    move(450, 3, 0.0004, 'left')
    wait(0.5)
    move_both(1700, 1, 2, 0.0002, 'down');   wait(0.5)
    move(850, 1, 0.0004, 'up');              wait(0.5)
    mix(2, 600, mode='normal', timer=True)   # 10 min lysis with beads
    wait(0.5)
    move(850, 2, 0.0004, 'up');              wait(0.5)

    # Gradual bead collection
    move_both(1000, 1, 2, 0.0002, 'down');   wait(30, timer=True)
    move_both(400,  1, 2, 0.0002, 'down');   wait(30, timer=True)
    move_both(300,  1, 2, 0.0002, 'down');   wait(30, timer=True)
    move_both(1700, 1, 2, 0.0002, 'up');     wait(0.5)

    # ── WASH 1 ─────────────────────────────────────────────────
    move(675, 3, 0.0004, 'right');           wait(0.5)
    move_both(1700, 1, 2, 0.0002, 'down');   wait(0.5)
    move(850, 1, 0.0004, 'up');              wait(0.5)
    mix(2, 600, mode='wash', timer=True)     # 10 min wash 1
    wait(0.5)
    move(850, 2, 0.0004, 'up');              wait(0.5)
    move_both(1600, 1, 2, 0.0002, 'down');   wait(30, timer=True)
    move_both(100,  1, 2, 0.0002, 'down');   wait(30, timer=True)
    move_both(1700, 1, 2, 0.0002, 'up');     wait(0.5)

    # ── WASH 2 → ELUTION (two-pass loop) ──────────────────────
    for pass_num in range(2):
        is_last = (pass_num == 1)

        if is_last:
            # ── ELUTION ────────────────────────────────────────
            move(230, 3, 0.0004, 'right');           wait(600, timer=True)
            move_both(1700, 1, 2, 0.0002, 'down');   wait(0.5)
            move(850, 1, 0.0004, 'up');              wait(0.5)
            mix(2, 300, mode='last', timer=True)     # 5 min elution
            wait(0.5)
            move(850, 2, 0.0004, 'up');              wait(0.5)
            move_both(1700, 1, 2, 0.0002, 'down');   wait(30, timer=True)
            move_both(1700, 1, 2, 0.0002, 'up');     wait(0.5)

        else:
            # ── WASH 2 ─────────────────────────────────────────
            move(220, 3, 0.0004, 'right');           wait(0.5)
            move_both(1700, 1, 2, 0.0002, 'down');   wait(0.5)
            move(850, 1, 0.0004, 'up');              wait(0.5)
            mix(2, 600, mode='wash', timer=True)     # 10 min wash 2
            wait(0.5)
            move(850, 2, 0.0004, 'up');              wait(0.5)
            move_both(1600, 1, 2, 0.0002, 'down');   wait(30, timer=True)
            move_both(100,  1, 2, 0.0002, 'down');   wait(30, timer=True)
            move_both(1700, 1, 2, 0.0002, 'up');     wait(0.5)


def run_motor_sequence_sputum():
    run_sequence(_sputum_steps, "Sputum")
