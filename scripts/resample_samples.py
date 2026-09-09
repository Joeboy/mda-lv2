#!/usr/bin/env python3
import math
import re
import sys


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: resample_samples.py INPUT OUTPUT FACTOR')

    input_path, output_path, factor_text = sys.argv[1:]
    factor = int(factor_text)
    if factor not in (1, 2, 3, 4):
        raise SystemExit('factor must be 1, 2, 3, or 4')

    with open(input_path, encoding='ascii') as source:
        source_text = source.read()
    match = re.search(r'\bshort\s+(\w+)\s*\[\s*\]\s*=\s*\{(.*)\};', source_text, re.S)
    if match is None:
        raise SystemExit('input does not contain a short array initializer')

    name, initializer = match.groups()
    samples = [int(value) for value in re.findall(r'-?\d+', initializer)]
    if factor > 1:
        samples = resample(samples, factor)
    with open(output_path, 'w', encoding='ascii') as output:
        output.write('short %s[] = {\n' % name)
        for offset in range(0, len(samples), 16):
            output.write(','.join(str(value) for value in samples[offset:offset + 16]))
            output.write(',\n' if offset + 16 < len(samples) else '\n')
        output.write('};\n')


def resample(samples, factor):
    radius = 4 * factor
    cutoff = 0.5 / factor
    output = []
    for position in range(0, len(samples), factor):
        weighted_sum = 0.0
        weight_sum = 0.0
        first = max(0, position - radius + 1)
        last = min(len(samples), position + radius)
        for source_position in range(first, last):
            distance = source_position - position
            window_position = (distance + radius - 1) / (2 * radius - 1)
            window = (0.42 - 0.5 * math.cos(2.0 * math.pi * window_position) +
                      0.08 * math.cos(4.0 * math.pi * window_position))
            argument = 2.0 * cutoff * distance
            sinc = 1.0 if argument == 0.0 else math.sin(math.pi * argument) / (math.pi * argument)
            weight = 2.0 * cutoff * sinc * window
            weighted_sum += samples[source_position] * weight
            weight_sum += weight
        output.append(int(round(weighted_sum / weight_sum)))
    return output


if __name__ == '__main__':
    main()