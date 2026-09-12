from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

import hunter_engine as h


def make_video(path: Path, frames=24, fps=12.0, w=480, hh=270):
    fourcc=cv2.VideoWriter_fourcc(*'MJPG')
    writer=cv2.VideoWriter(str(path), fourcc, fps, (w,hh))
    assert writer.isOpened()
    colors=[(0,0,255),(0,180,255),(0,255,0),(255,0,0),(255,0,255),(255,255,0)]
    xs=[70,130,190,250,310,370]
    for fi in range(frames):
        frame=np.zeros((hh,w,3),np.uint8)
        for i,(x,c) in enumerate(zip(xs,colors)):
            xx=x+int(fi*0.8)+(i%2)
            yy=85+i*20 + int(3*np.sin(fi/4+i))
            cv2.circle(frame,(xx,yy),13,c,-1)
            cv2.circle(frame,(xx,yy),13,(255,255,255),1)
        writer.write(frame)
    writer.release()
    return path


def detector_cfg():
    return {'min_radius':8,'max_radius':20,'param1':120,'param2':45,'use_color_contours':True}


def tracker_cfg():
    return {'max_distance':35,'max_missed':3}


def test_clip_and_canonical_hash_are_deterministic():
    assert h.clip(-1)==0 and h.clip(2)==1
    assert h.canonical_hash({'b':2,'a':1})==h.canonical_hash({'a':1,'b':2})


def test_mask_frame_keeps_only_chamber_and_zeroes_overlay():
    frame=np.full((100,120,3),255,np.uint8)
    out=h.mask_frame(frame,(10,20,100,90),[(30,40,50,60)])
    assert out[0,0].sum()==0
    assert out[25,15].sum()>0
    assert out[45,35].sum()==0


def test_markov_absorption_propagates(tmp_path):
    p=tmp_path/'m.json'
    p.write_text(json.dumps({'states':['A','E'],'transition':[[0.5,0.5],[0,1]]}))
    m=h.MarkovModel.load(p)
    assert m.absorption_probability('A',1)==pytest.approx(0.5)
    assert m.absorption_probability('A',3)==pytest.approx(0.875)
    assert m.absorption_probability('missing',3)==0


def test_external_global_assignment_is_one_to_one():
    probs={
        'track_ids':[10,20,30],
        'numbers':[7,14,23],
        'probabilities':[
            [0.9,0.08,0.02],
            [0.8,0.19,0.01],
            [0.01,0.04,0.95],
        ]
    }
    out=h.resolve_external_identity_probs(probs)
    assert out[10]==7
    assert out[20]==14
    assert out[30]==23
    assert len(set(out.values()))==3


def test_ocr_posterior_assigns_strong_evidence_and_abstains_weak():
    obs={
        1:[{'number':7,'confidence':90},{'number':7,'confidence':80},{'number':14,'confidence':5}],
        2:[{'number':14,'confidence':88},{'number':14,'confidence':85}],
        3:[{'number':23,'confidence':9}],
    }
    out,diag=h.identity_probabilities_from_ocr(obs)
    assert out[1]==7
    assert out[2]==14
    assert 3 not in out
    assert 3 in diag['abstained']


def test_recovery_state_loads_recovered_reliability_profile():
    recovery=Path(__file__).resolve().parents[1]/'recovery'
    r=h.RecoveryState(recovery)
    assert r.audit()['legacy_state_present'] is True
    assert 'M1_VISUAL' in r.legacy_reliability
    assert 0 <= r.legacy_reliability['M1_VISUAL'] <= 1


def test_lock_binds_input_config_and_report(tmp_path):
    report={'version':'v','input_sha256':'abc','config_sha256':'def','top6':[1,2,3,4,5,6]}
    p=tmp_path/'prediction.json'; h.save_report(report,p)
    lock=h.lock_report(p)
    d=json.loads(lock.read_text())
    assert d['input_sha256']=='abc'
    assert d['config_sha256']=='def'
    assert d['report_sha256']==h.sha256_file(p)
    assert d['random_ticket_fallback'] is False
    assert d['post_draw_adjustment'] is False


def test_detector_finds_colored_round_objects():
    img=np.zeros((220,320,3),np.uint8)
    cv2.circle(img,(80,90),18,(0,0,255),-1)
    cv2.circle(img,(200,130),16,(0,255,0),-1)
    d=h.EnsembleBallDetector(min_radius=10,max_radius=25,param2=50,use_color_contours=True).detect(img,0)
    centers=[(x.x,x.y) for x in d]
    assert any(abs(x-80)<5 and abs(y-90)<5 for x,y in centers)
    assert any(abs(x-200)<5 and abs(y-130)<5 for x,y in centers)


def test_synthetic_video_hard_cutoff_no_random_completion(tmp_path):
    v=make_video(tmp_path/'synth.avi')
    report=h.analyze_video(
        v,(330,40,470,240),chamber_roi=(0,0,480,270),cutoff_seconds=1.0,
        recovery_dir=Path(__file__).resolve().parents[1]/'recovery',auto_ocr=False,
        detector_config=detector_cfg(),tracker_config=tracker_cfg(),
    )
    assert report['video']['frames_processed']==12
    assert report['random_ticket_fallback'] is False
    assert report['post_draw_adjustment'] is False
    assert report['top6']==[]
    assert report['top6_status']=='insufficient_numbered_tracks'
    assert report['detector']['tracks_total']>=6


def test_synthetic_video_direct_map_produces_locked_candidate(tmp_path):
    v=make_video(tmp_path/'synth.avi')
    report=h.analyze_video(
        v,(330,40,470,240),identity_map={1:4,2:11,3:19,4:27,5:36,6:44},
        chamber_roi=(0,0,480,270),cutoff_seconds=1.0,recovery_dir=Path(__file__).resolve().parents[1]/'recovery',
        auto_ocr=False,detector_config=detector_cfg(),tracker_config=tracker_cfg(),
    )
    assert report['identity_mode']=='direct_map'
    assert report['top6_status']=='locked_candidate'
    assert report['top6']==[4,11,19,27,36,44]
    assert report['config_sha256']
    assert report['input_sha256']==h.sha256_file(v)


def test_repeatability_same_video_same_ranking(tmp_path):
    v=make_video(tmp_path/'synth.avi')
    kw=dict(
        extraction_zone=(330,40,470,240),identity_map={1:4,2:11,3:19,4:27,5:36,6:44},
        chamber_roi=(0,0,480,270),cutoff_seconds=1.0,recovery_dir=Path(__file__).resolve().parents[1]/'recovery',
        auto_ocr=False,detector_config=detector_cfg(),tracker_config=tracker_cfg(),
    )
    a=h.analyze_video(v,**kw); b=h.analyze_video(v,**kw)
    assert a['config_sha256']==b['config_sha256']
    assert a['input_sha256']==b['input_sha256']
    assert a['top6']==b['top6']
    pa=[(x['track_id'],round(x['score'],12),x['number']) for x in a['anonymous_track_ranking']]
    pb=[(x['track_id'],round(x['score'],12),x['number']) for x in b['anonymous_track_ranking']]
    assert pa==pb


def test_score_locked_report():
    report={'top6':[1,2,3,4,5,6],'anonymous_track_ranking':[{'number':x} for x in [1,7,2,8,3,9,4,10,5,11,6]]}
    s=h.score_locked_report(report,[1,2,3,20,21,22])
    assert s['top6_hits']==3
    assert s['top10_capture']==3
    assert s['top15_capture']==3
    with pytest.raises(ValueError):
        h.score_locked_report(report,[1,2,3])


def test_tesseract_probe_is_boolean_and_safe():
    assert isinstance(h._tesseract_available(),bool)


def test_validated_frequency_accepts_stable_2hz_rejects_boundary_cycle():
    fps=25.0
    t=np.arange(100)/fps
    good=100+30*np.sin(2*np.pi*2.0*t)+2*t
    g=h._validated_frequency(good,fps)
    assert g['validated'] is True
    assert g['frequency_hz']==pytest.approx(2.0,abs=0.26)
    slow=100+30*np.sin(2*np.pi*0.25*t)
    b=h._validated_frequency(slow,fps)
    assert b['validated'] is False
    assert b['frequency_hz'] is None
