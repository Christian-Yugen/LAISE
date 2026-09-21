from __future__ import annotations
import numpy as np

class MixIntelligence:
    """
    LAISE T008 v0.1.1
    Conditional low-mid masking control + percussion-triggered ducking.

    The cleanup detector is relative to the programme material itself rather
    than to an arbitrary absolute FFT magnitude. This keeps the decision
    content-aware across different SoundFonts/gain structures.
    """
    def __init__(self,sr=48000):
        self.sr=sr

    def _conditional_band_process(self,x,lo,hi,max_cut_db=-2.0,
                                  frame=2048,hop=1024,
                                  dominance_threshold=0.18,
                                  activity_percentile=55.0):
        if x.ndim != 2 or x.shape[0] != 2:
            raise ValueError("Expected stereo array shaped (2, samples).")

        win=np.hanning(frame).astype(np.float32)
        freqs=np.fft.rfftfreq(frame,1/self.sr)
        band=(freqs>=lo)&(freqs<=hi)
        audible=(freqs>=60)&(freqs<=12000)

        analyses=[]
        for pos in range(0,max(1,x.shape[1]-frame+1),hop):
            seg=x[:,pos:pos+frame]
            if seg.shape[1]<frame:break
            mono=np.mean(seg,axis=0)*win
            mag=np.abs(np.fft.rfft(mono))
            band_energy=float(np.sum(mag[band]**2))
            total_energy=float(np.sum(mag[audible]**2))+1e-20
            rms=float(np.sqrt(np.mean(mono.astype(np.float64)**2)+1e-20))
            analyses.append((pos,band_energy/total_energy,rms))

        if not analyses:
            return x.copy(),0,{"activity_threshold":0.0,"max_dominance":0.0}

        active=[a[2] for a in analyses if a[2]>1e-8]
        activity_threshold=float(np.percentile(active,activity_percentile)) if active else 0.0

        y=np.zeros_like(x,dtype=np.float32)
        norm=np.zeros(x.shape[1],np.float32)
        applied=0
        max_dom=max(a[1] for a in analyses)

        for pos,dominance,rms in analyses:
            seg=x[:,pos:pos+frame]
            # Conditional: only attenuate when the programme is active AND
            # the 200–450 Hz band occupies a meaningful share of its spectrum.
            excess=max(0.0,dominance-dominance_threshold)
            scale=min(1.0,excess/max(1e-9,0.42-dominance_threshold))
            cut_db=max_cut_db*scale if rms>=activity_threshold and scale>0 else 0.0
            g=10**(cut_db/20.0)

            for c in range(2):
                S=np.fft.rfft(seg[c]*win)
                S[band]*=g
                rec=np.fft.irfft(S,n=frame).astype(np.float32)
                y[c,pos:pos+frame]+=rec*win
            norm[pos:pos+frame]+=win*win
            if cut_db<-.05:applied+=1

        nz=norm>1e-7
        y[:,nz]/=norm[nz]
        y[:,~nz]=x[:,~nz]
        return y,applied,{"activity_threshold":activity_threshold,
                          "max_dominance":float(max_dom),
                          "dominance_threshold":dominance_threshold}

    def conditional_lowmid_cleanup(self,x,lo=200,hi=450,max_cut_db=-2.0):
        return self._conditional_band_process(x,lo,hi,max_cut_db)

    def percussion_duck(self,x,trigger,max_duck_db=-2.0,attack_ms=8,release_ms=150):
        n=min(x.shape[1],trigger.shape[1])
        mono=np.max(np.abs(trigger[:,:n]),axis=0)
        a=np.exp(-1/(self.sr*attack_ms/1000))
        r=np.exp(-1/(self.sr*release_ms/1000))
        env=np.zeros(n,np.float32)
        for i in range(1,n):
            coef=a if mono[i]>env[i-1] else r
            env[i]=coef*env[i-1]+(1-coef)*mono[i]
        ref=np.percentile(env,92)+1e-9
        amount=np.clip(env/ref,0,1)
        gain=10**((max_duck_db*amount)/20)
        y=x.copy();y[:,:n]*=gain
        return y,float(np.min(gain))

    def preserve_dynamic_range(self,mix,ceiling=.90):
        peak=float(np.max(np.abs(mix)))
        if peak>ceiling:
            mix=mix*(ceiling/peak)
        return mix
