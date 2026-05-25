#!/usr/bin/env python3
"""Quick standalone vocoder health check that prints useful error details."""
import sys, os

# Quick dependency check
try:
    import flask, numpy, scipy
    print(f"[deps] OK: flask={flask.__version__} numpy={numpy.__version__} scipy={scipy.__version__}")
except ImportError as e:
    print(f"[deps] MISSING: {e}")
    sys.exit(1)

from pathlib import Path
from flask import Flask, request, jsonify
import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
import hashlib, math, random

app = Flask("RedDirt-Vocoder")
SR = 48000
VOWELS = {
    "a":  ([800, 1200, 2500],[80,120,200]),
    "e":  ([600,1900,2500],[80,120,200]),
    "i":  ([300,2300,3000],[80,120,200]),
    "o":  ([500,900,2500],[80,120,200]),
    "u":  ([350,700,2500],[80,120,200]),
    "ae": ([700,1600,2500],[80,120,200]),
    "ao": ([600,950,2500],[80,120,200]),
    "uh": ([500,1400,2500],[80,120,200]),
    "y":  ([400,2000,2800],[80,120,200]),
}

def midi_to_hz(note:int)->float:
    return 440.0*(2.0**((note-69)/12.0))

def _peak_filter_excited(excitation:np.ndarray, f0:float, bw:float, sr:int=SR, f_amp:float=1.0)->np.ndarray:
    w0=2.0*math.pi*f0/sr
    alpha=math.sin(w0)*math.sinh(math.log(2.0)/2.0*bw*w0/math.sin(w0))
    b0= alpha; b1=0.0; b2=-alpha
    a0= 1.0+alpha; a1=-2.0*math.cos(w0); a2=1.0-alpha
    b=np.array([b0/a0,b1/a0,b2/a0])
    a=np.array([1.0,a1/a0,a2/a0])
    return lfilter(b,a,excitation)*f_amp

def _sawtooth_wave(length:int,freq:float,sr:int=SR,vibrato_rate:float=5.5,vibrato_depth:float=0.15)->np.ndarray:
    t=np.arange(length,dtype=np.float64)/sr
    mod=vibrato_depth*np.sin(2.0*math.pi*vibrato_rate*t)
    inst_freq=freq*(1.0+mod)
    phase=np.cumsum(2.0*math.pi*inst_freq/sr)
    out=np.zeros(length,dtype=np.float64)
    n_harm=min(40,int(sr/(2.0*freq)))
    for h in range(1,n_harm+1):
        amp=(-1.0)**(h+1)/h
        out+=amp*np.sin(phase*h)
    out*=0.3
    return out.astype(np.float32)

def _noise(length:int,amp:float=0.05)->np.ndarray:
    return (np.random.randn(length).astype(np.float32)*amp)

def _word_to_phonemes(text:str):
    text=text.lower()
    return [ch for ch in text if ch in "aeiou"] or ["uh"]

def _interpolate_pitch(notes,sr=SR,tempo=65.0):
    beat_dur_s=60.0/tempo
    total_s=sum(n.get("duration_beat",0.5) for n in notes)*beat_dur_s
    total_samples=int(total_s*sr)
    if total_samples<1024: total_samples=1024
    boundaries=[0]
    for n in notes:
        boundaries.append(boundaries[-1]+int(n.get("duration_beat",0.5)*beat_dur_s*sr))
    boundaries=np.array(boundaries)
    boundaries=np.clip(boundaries,0,total_samples)
    contour=np.zeros(total_samples,dtype=np.float32)
    for i,n in enumerate(notes):
        s=boundaries[i]; e=boundaries[i+1]
        if e<=s: continue
        hz=midi_to_hz(n.get("pitch",69))
        if i>0:
            prev=midi_to_hz(notes[i-1].get("pitch",69))
            t=min(2048,int(e-s))
            contour[s:s+t]=np.linspace(prev,hz,t)
            contour[s+t:e]=hz
        else:
            contour[s:e]=hz
    last=int(boundaries[len(notes)]) if len(notes)<len(boundaries) else 0
    if last<total_samples and notes: contour[last:]=midi_to_hz(notes[-1].get("pitch",69))
    return contour

def synthesize_singing(lyrics:str,notes,emotion="sad",singer_id="female_1",sr=SR):
    phonemes=_word_to_phonemes(lyrics)
    tempo=65.0
    beat_dur_s=60.0/tempo
    total_s=sum(n.get("duration_beat",0.5) for n in notes)*beat_dur_s
    total_samples=int(max(1,total_s)*sr)
    if total_samples<1024: total_samples=1024
    contour=_interpolate_pitch(notes,sr,tempo)
    excitation=np.zeros(total_samples,dtype=np.float32)
    spp=max(1,total_samples//len(phonemes))
    for idx,ph in enumerate(phonemes):
        s=idx*spp; e=min(s+spp,total_samples); l=e-s
        if l<=0: continue
        avg=float(np.mean(contour[s:e])) if np.mean(contour[s:e])>0 else 220.0
        saw=_sawtooth_wave(l,avg,sr,vibrato_rate=5.5+float(np.random.randn())*0.5,
                           vibrato_depth=0.2 if emotion=="sad" else 0.1)
        breathiness=0.15 if emotion=="sad" else 0.05
        noise=_noise(l,amp=breathiness)
        if idx>0 and l>512:
            bl=min(256,l)
            noise[:bl]+=_noise(bl,amp=0.3)
        excitation[s:e]=saw+noise
    formant_out=excitation.copy().astype(np.float64)
    vkey=phonemes[0] if phonemes[0] in VOWELS else "uh"
    freqs,bws=VOWELS[vkey]
    shift=1.15 if "female" in singer_id else 0.85 if "male" in singer_id else 1.0
    for f,bw in zip(freqs,bws):
        formant_out+=_peak_filter_excited(excitation,f*shift,bw,sr,1.0)
    formant_out+=_peak_filter_excited(excitation,250*shift,100,sr,0.6)
    formant_out=np.tanh(formant_out*2.0)
    fade=min(2048,total_samples//4)
    if fade>1:
        formant_out[:fade]*=np.linspace(0.0,1.0,fade)
        formant_out[-fade:]*=np.linspace(1.0,0.0,fade)
    return formant_out.astype(np.float32)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"ok","backend":"parallel_formant","model":"vocoder","device":"CPU"})

@app.route("/sing", methods=["POST"])
def sing():
    data=request.get_json()
    if data is None: return jsonify({"status":"error","message":"No JSON"}),400
    lyrics=data.get("lyrics","La")
    notes=data.get("notes",[])
    sid=data.get("singer_id","female_1")
    em=data.get("emotion","sad")
    od=Path(data.get("output_dir",".reddirt/output"))
    od.mkdir(parents=True,exist_ok=True)
    if not notes: notes=[{"pitch":69,"duration_beat":0.5}]
    audio=synthesize_singing(lyrics,notes,em,sid)
    hid=hashlib.md5(lyrics.encode()).hexdigest()[:8]
    p=od/f"vocoder_{hid}.wav"
    wavfile.write(str(p),SR,audio)
    return jsonify({"status":"ok","audio_path":str(p),"backend":"parallel_formant",
        "metadata":{"lyrics":lyrics,"singer":sid,"emotion":em,
        "duration_sec":round(len(audio)/SR,2),"sample_rate":SR,"num_notes":len(notes)}})

if __name__=="__main__":
    import socket
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1",8766))
        s.close()
        print("[vocoder] Starting on port 8766")
    except OSError as e:
        print(f"[vocoder] Port 8766 already in use or unavailable: {e}")
        sys.exit(1)
    app.run(host="127.0.0.1",port=8766,debug=False,threaded=True)
