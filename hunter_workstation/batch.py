from __future__ import annotations
import argparse, json
from pathlib import Path
from hunter_engine import analyze_video, save_report, lock_report

EXT={'.mp4','.mov','.m4v','.avi','.mkv','.webm'}

def main():
    ap=argparse.ArgumentParser(description='Chronological Saturday Lotto Hunter batch runner')
    ap.add_argument('--input',required=True)
    ap.add_argument('--out',default='batch_runs')
    ap.add_argument('--cutoff',type=float,required=True,help='Hard pre-reveal cutoff seconds applied to each video')
    ap.add_argument('--chamber',default=None,help='x0,y0,x1,y1; default full frame')
    ap.add_argument('--extraction',required=True,help='x0,y0,x1,y1 extraction zone')
    ap.add_argument('--no-ocr',action='store_true')
    args=ap.parse_args()
    def rect(s): return tuple(float(x) for x in s.split(',')) if s else None
    root=Path(args.input); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    videos=sorted([p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in EXT], key=lambda p:p.name)
    index=[]
    for i,p in enumerate(videos,1):
        run=out/f'{i:04d}_{p.stem}'; run.mkdir(parents=True,exist_ok=True)
        try:
            report=analyze_video(p,rect(args.extraction),chamber_roi=rect(args.chamber),cutoff_seconds=args.cutoff,recovery_dir='recovery',auto_ocr=not args.no_ocr)
            rp=run/'prediction.json'; save_report(report,rp); lp=lock_report(rp)
            index.append({'video':str(p),'status':'ok','prediction':str(rp),'lock':str(lp),'top6':report.get('top6'),'top6_status':report.get('top6_status')})
        except Exception as ex:
            index.append({'video':str(p),'status':'error','error':str(ex)})
    (out/'batch_index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
    print(json.dumps({'videos':len(videos),'completed':sum(x['status']=='ok' for x in index),'failed':sum(x['status']!='ok' for x in index)},indent=2))

if __name__=='__main__': main()
