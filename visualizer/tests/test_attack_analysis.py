"""Synthetic evidence that fast repeated hits survive analysis without extra drops."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec = importlib.util.spec_from_file_location('build_audio_cues', Path(__file__).parents[1]/'tools/build_audio_cues.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class AttackAnalysisTests(unittest.TestCase):
    def test_three_fast_hits_and_strength_order(self):
        rate = 16000
        time = np.arange(rate)/rate
        signal = np.zeros_like(time)
        hits = [0.20,0.32,0.44]
        for onset,amplitude in zip(hits,[0.2,0.4,0.8]):
            age = time-onset
            envelope = np.where(age>=0,np.exp(-np.maximum(age,0)/0.025),0)
            signal += amplitude*envelope*np.cos(2*np.pi*95*age)
        events = analysis.detect_attacks(signal.astype(np.float32))
        self.assertEqual(len(events),3,events)
        for (actual,_),expected in zip(events,hits):
            self.assertLess(abs(actual-expected),0.025)
        self.assertTrue(events[0][1]<events[1][1]<events[2][1])

    def test_sustained_tone_does_not_generate_continuous_hits(self):
        time = np.arange(32000)/16000
        signal = (0.2*np.sin(2*np.pi*220*time)).astype(np.float32)
        events = analysis.detect_attacks(signal,percussive=False)
        self.assertLessEqual(len(events),1,events)

    def test_spatial_projection_uses_automation_not_emitter_order(self):
        role = {'keyframes':[{'time_seconds':0,'azimuth_deg_unwrapped':-90,'elevation_deg':0},
            {'time_seconds':2,'azimuth_deg_unwrapped':90,'elevation_deg':0}],
            'distance_keyframes':[{'time_seconds':0,'distance_m':1}]}
        left=analysis.floor_position(role,0)
        middle=analysis.floor_position(role,1)
        right=analysis.floor_position(role,2)
        self.assertLess(left[0],0)
        self.assertAlmostEqual(middle[0],0)
        self.assertGreater(right[0],0)
        self.assertLess(middle[1],0)


if __name__ == '__main__':
    unittest.main()
