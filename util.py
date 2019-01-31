from typing import Dict


def compare_buffer(buffer1, buffer2):
    if len(buffer1) != len(buffer2):
        return f"size changed!! {len(buffer1)} -> {len(buffer2)}"
    else:
        difs: Dict[int, list] = {}
        i = 0
        diff_started = False
        diff_start = -1
        while i < len(buffer1):
            if diff_started:
                if buffer1[i] == buffer2[i]:
                    last_index = i - 1
                    difs[diff_start] = [last_index, buffer1[diff_start:i], buffer2[diff_start:i]]
                    diff_started = False
            elif buffer1[i] != buffer2[i]:
                diff_started = True
                diff_start = i
            i += 1
        if difs:
            s = "found difs: "
            for start in difs:
                s += f"from {start} to {difs[start][0]} changed {difs[start][1]} to {difs[start][2]}"
        else:
            s = "no difs"
        return s
