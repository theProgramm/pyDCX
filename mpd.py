import subprocess


def set_volume(v: int):
    if not 0 <= v <= 100:
        raise ValueError("volume should be in rage [0,100]")
    subprocess.run(["mpc", "volume", str(v)])
