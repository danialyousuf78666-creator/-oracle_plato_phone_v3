from __future__ import annotations

import argparse
import json
from pathlib import Path

from hunter_engine import analyze_video, save_report, lock_report

EXT={'.mp4','.mov','.m4v','.avi','.mkv','.webm'}


def main():
    ap=argparse.ArgumentParser(description='Chronological Saturday Lotto Hunter v0.5 batch runner')
    ap.add_argument('--input',required=True)
    ap.add_argument('--out',default='batch_runs')
    cut=ap.add_mutually_exclusive_group(required=True)
    cut.add_argument('--cutoff',type=float,help='One PRE-EXTRACTION cutoff in seconds for every video')
    cut.add_argument('--cutoff-manifest',help='JSON mapping filename (or stem) to PRE-EXTRACTION cutoff seconds')
    ap.add_argument('--verified-pre-extraction',action='store_true',help='Required acknowledgement: cutoffs contain no extracted winning ball/result evidence')
    ap.add_argument('--chamber',default=None,help='x0,y0,x1,y1; default full frame')
    ap.add_argument('--extraction',required=True,help='x0,y0,x1,y1 extraction path/zone')
    ap.add_argument('--no-ocr',action='store_true')
    ap.add_argument('--min-radius',type=int,default=5)
    ap.add_argument('--max-radius',type=int,default=40)
    ap.add_argument('--hough-p2',type=float,default=20.0)
    ap.add_argument('--max-distance',type=float,default=45.0)
    ap.add_argument('--max-missed',type=int,default=8)
    args=ap.parse_args()

    if not args.verified_pre_extraction:
        ap.error('--verified-pre-extraction is required; Hunter will not batch-run unverified cutoffs')

    def rect(s):
        if not s: return None
        vals=tuple(float(x) for x in s.split(','))
        if len(vals)!=4: raise ValueError('rectangles must contain x0,y0,x1,y1')
        return vals

    manifest={}
    if args.cutoff_manifest:
        manifest=json.loads(Path(args.cutoff_manifest).read_text(encoding='utf-8'))
        if not isinstance(manifest,dict):
            raise ValueError('cutoff manifest must be a JSON object')

    root=Path(args.input); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    videos=sorted([p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in EXT], key=lambda p:p.name)
    index=[]
    for i,p in enumerate(videos,1):
        run=out/f'{i:04d}_{p.stem}'; run.mkdir(parents=True,exist_ok=True)
        try:
            cutoff=float(args.cutoff) if args.cutoff is not None else manifest.get(p.name,manifest.get(p.stem))
            if cutoff is None or float(cutoff)<=0:
                raise ValueError('no valid pre-extraction cutoff for this video')
            report=analyze_video(
                p,
                rect(args.extraction),
                chamber_roi=rect(args.chamber),
                cutoff_seconds=float(cutoff),
                cutoff_verified_by_operator=True,
                recovery_dir='recovery',
                auto_ocr=not args.no_ocr,
                detector_config={
                    'min_radius':args.min_radius,'max_radius':args.max_radius,
                    'param2':args.hough_p2,'use_color_contours':True,
                },
                tracker_config={
                    'max_distance':args.max_distance,'max_missed':args.max_missed,
                    'velocity_window':5,'radius_weight':0.35,'max_radius_change':0.65,'gap_growth':0.20,
                },
            )
            rp=run/'prediction.json'; save_report(report,rp); lp=lock_report(rp)
            index.append({
                'video':str(p),'status':'ok','cutoff_seconds':float(cutoff),
                'prediction':str(rp),'lock':str(lp),'top6':report.get('top6'),
                'top6_status':report.get('top6_status'),'quality_gate':report.get('quality_gate'),
            })
        except Exception as ex:
            index.append({'video':str(p),'status':'error','error':str(ex)})
    (out/'batch_index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
    print(json.dumps({
        'videos':len(videos),'completed':sum(x['status']=='ok' for x in index),
        'failed':sum(x['status']!='ok' for x in index),
        'locked_candidates':sum(x.get('top6_status')=='locked_candidate' for x in index),
        'abstentions':sum(x.get('status')=='ok' and x.get('top6_status')!='locked_candidate' for x in index),
    },indent=2))


if __name__=='__main__':
    main()
