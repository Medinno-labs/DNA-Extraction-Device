"""
stool_control.py — DNA extraction sequence for Stool samples.
"""

from sequence_helpers import run_sequence, check, move, move_both, wait, mix


def _stool_steps():
    # ── INITIAL POSITIONING ────────────────────────────────────
    move(2257, 3, 0.0004, 'right');          wait(0.5)
    move(450,  3, 0.0004, 'right');          wait(0.5)
    move(800,  2, 0.0004, 'down');           wait(0.5)

    # ── LYSIS MIX ──────────────────────────────────────────────
    mix(2, 60, timer=True)
    wait(0.5)
    move(820, 2, 0.0004, 'up');             wait(0.5)

    # ── BEAD COLLECTION ────────────────────────────────────────
    move_both(1000, 1, 2, 0.0002, 'down');  wait(30, timer=True)
    move_both(400,  1, 2, 0.0002, 'down');  wait(30, timer=True)
    move_both(220,  1, 2, 0.0002, 'down');  wait(60, timer=True)
    move_both(1620, 1, 2, 0.0002, 'up');    wait(0.5)

    # ── BEAD BINDING ───────────────────────────────────────────
    move(225, 3, 0.0004, 'right');          wait(0.5)
    move_both(1620, 1, 2, 0.0002, 'down'); wait(0.5)
    move(800, 1, 0.0004, 'up');            wait(0.5)
    mix(2, 60, timer=True)
    wait(0.5)
    move(820, 2, 0.0004, 'up');            wait(0.5)
    move_both(1450, 1, 2, 0.0002, 'down'); wait(60, timer=True)
    move_both(170,  1, 2, 0.0002, 'down'); wait(60, timer=True)
    move_both(1620, 1, 2, 0.0002, 'up');   wait(0.5)

    # ── WASH → ELUTION (two-pass loop) ────────────────────────
    for pass_num in range(2):
        is_last = (pass_num == 1)

        if is_last:
            # ── ELUTION ────────────────────────────────────────
            move(230, 3, 0.0004, 'right');           wait(60, timer=True)
            move_both(1620, 1, 2, 0.0002, 'down');   wait(0.5)
            move(800, 1, 0.0004, 'up');              wait(0.5)
            mix(2, 60, mode='last', timer=True)
            wait(0.5)
            move(820, 2, 0.0004, 'up');              wait(0.5)
            move_both(1640, 1, 2, 0.0002, 'down');   wait(60, timer=True)
            move_both(1640, 1, 2, 0.0002, 'up');     wait(0.5)

        else:
            # ── WASH ───────────────────────────────────────────
            move(220, 3, 0.0004, 'right');           wait(0.5)
            move_both(1620, 1, 2, 0.0002, 'down');   wait(0.5)
            move(800, 1, 0.0004, 'up');              wait(0.5)
            mix(2, 60, timer=True)
            wait(0.5)
            move(820, 2, 0.0004, 'up');              wait(0.5)
            move_both(1450, 1, 2, 0.0002, 'down');   wait(60, timer=True)
            move_both(170,  1, 2, 0.0002, 'down');   wait(60, timer=True)
            move_both(1620, 1, 2, 0.0002, 'up');     wait(0.5)


def run_motor_sequence_stool():
    run_sequence(_stool_steps, "Stool")
