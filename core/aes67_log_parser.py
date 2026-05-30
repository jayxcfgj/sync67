"""PipeWire-AES67 Log-Parser – erkennt bekannte Warnungen/Fehler und zählt sie."""

import re

LOG_PATTERNS = [
    {
        'key': 'overrun_read',
        'label': 'Overruns (read)',
        'pattern': re.compile(r'receiver read overrun (\d+) > (\d+)'),
        'severity': 'warning',
        'summary': 'Receiver buffer overrun – audio data arrives faster than it can be processed.',
        'advice': 'Increase sess.latency.msec or check PTP clock synchronisation.',
    },
    {
        'key': 'overrun_write',
        'label': 'Overruns (write)',
        'pattern': re.compile(r'sender write overrun (\d+) \+ (\d+) > (\d+)/(\d+)'),
        'severity': 'warning',
        'summary': 'Sender buffer full – audio data cannot be written into the ring buffer.',
        'advice': 'Check network bandwidth or reduce sample rate / quantum size.',
    },
    {
        'key': 'timeout_miss',
        'label': 'Timeout misses',
        'pattern': re.compile(r'missing timeout (\d+)'),
        'severity': 'warning',
        'summary': 'A scheduled timeout was missed – the audio graph could not keep up.',
        'advice': 'Reduce DSP load, increase quantum size, or check system CPU frequency scaling.',
    },
    {
        'key': 'timestamp_err',
        'label': 'Timestamp errors',
        'pattern': re.compile(r'timestamp: expected (\d+) != actual (\d+)'),
        'severity': 'error',
        'summary': 'PTP timestamp mismatch – expected and actual clock values differ.',
        'advice': 'PTP clock synchronisation issue. Check ptp4l status and network connectivity.',
    },
    {
        'key': 'out_of_buffers',
        'label': 'Out of buffers',
        'pattern': re.compile(r'out of buffers'),
        'severity': 'error',
        'summary': 'PipeWire stream could not dequeue a buffer – system under memory pressure.',
        'advice': 'Check DSP load, reduce number of streams, or increase system memory limits.',
    },
]


class AES67LogParser:
    def __init__(self):
        self.counters = {p['key']: 0 for p in LOG_PATTERNS}
        self.other_count = 0
        self.severity_counts = {'info': 0, 'warning': 0, 'error': 0}
        self.last_info = {}

    def parse_line(self, line):
        for p in LOG_PATTERNS:
            m = p['pattern'].search(line)
            if m:
                self.counters[p['key']] += 1
                self.severity_counts[p['severity']] += 1
                self.last_info = {
                    'severity': p['severity'],
                    'summary': p['summary'],
                    'advice': p['advice'],
                    'timestamp': self._extract_ts(line),
                    'raw': line.strip(),
                }
                return self.last_info['severity'], p['key']
        stripped = line.strip()
        if stripped:
            self.other_count += 1
            self.last_info = {
                'severity': 'info',
                'summary': stripped[:120],
                'advice': '',
                'timestamp': self._extract_ts(line),
                'raw': stripped,
            }
        return None

    def reset_counter(self, key):
        if key in self.counters:
            self.counters[key] = 0
        elif key == 'other':
            self.other_count = 0
        self.severity_counts = {'info': 0, 'warning': 0, 'error': 0}
        for k in self.counters:
            self.severity_counts['warning' if k in ('overrun_read', 'overrun_write', 'timeout_miss') else 'error'] += self.counters[k]
        if self.other_count > 0:
            self.severity_counts['info'] += self.other_count

    def reset_all(self):
        for k in self.counters:
            self.counters[k] = 0
        self.other_count = 0
        self.severity_counts = {'info': 0, 'warning': 0, 'error': 0}
        self.last_info = {}

    @property
    def total(self):
        return sum(self.counters.values()) + self.other_count

    @property
    def aggregate_severity(self):
        if self.severity_counts['error'] > 0:
            return 'error'
        if self.severity_counts['warning'] > 0:
            return 'warning'
        return 'info'

    def _extract_ts(self, line):
        m = re.search(r'\[(\d{2}:\d{2}:\d{2}\.\d+)\]', line)
        return m.group(1) if m else ''
