"""Capture a captioned 2:45 MOCK rehearsal using the actual static judge build.
Run in an offline Playwright/FFmpeg container on the authorized rendering host.
"""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import time
from playwright.sync_api import sync_playwright

ENTRY = Path(__file__).resolve().parents[1]
STYLE = """body{margin:0;background:#0c1417;color:#edf6f6;font:28px/1.5 system-ui,sans-serif}
.card{padding:140px 90px}h1{font-size:64px;color:#baf790;margin:0 0 20px}p{max-width:1020px}
#draft-mark{position:fixed;z-index:10000;top:0;left:0;right:0;background:#ffd08b;color:#201a12;padding:6px 24px;font:bold 18px system-ui}
#caption{position:fixed;z-index:10000;bottom:0;left:0;right:0;background:#081014f5;color:#edf6f6;padding:16px 32px;font:24px/1.4 system-ui;min-height:100px}
"""


def render(output, ffmpeg='ffmpeg'):
    capture=json.loads((output/'capture-results.json').read_text())
    sources=list((output/'raw').glob('*.webm'))
    if len(sources)!=1 or capture.get('draft_mock') is not True or capture.get('external_requests')!=[]:
        raise ValueError('Expected one mock capture with zero external requests')
    source=sources[0]
    movie=output/'signaldesk-draft-mock.mp4'
    subprocess.run([ffmpeg,'-y','-v','error','-ss',str(capture.get('lead_in_seconds',0)),'-i',str(source),'-t','165','-vf','fps=25',
        '-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(movie)],check=True)
    verify_movie(output, ffmpeg, capture)


def verify_movie(output, ffmpeg, capture):
    movie=output/'signaldesk-draft-mock.mp4'
    decoded=subprocess.run([ffmpeg,'-v','error','-i',str(movie),'-progress','pipe:1','-nostats','-f','null','-'],
        check=True,capture_output=True,text=True)
    # Use the same codec-capable binary for encoding and full decoding. Some
    # distro ffprobe builds lack an operational H.264 decoder.
    timestamps=[int(line.split('=',1)[1]) for line in decoded.stdout.splitlines()
        if line.startswith('out_time_us=') and line.split('=',1)[1].isdigit()]
    if not timestamps:
        raise ValueError('Decoder did not report a final media timestamp')
    duration=max(timestamps)/1_000_000
    assert 160 <= duration <= 170, duration
    subprocess.run([ffmpeg,'-y','-v','error','-i',str(movie),'-vf','fps=1/20,scale=384:-1,tile=2x4','-frames:v','1',str(output/'contact-sheet.png')],check=True)
    (output/'video-results.json').write_text(json.dumps({'duration_seconds':duration,'decode_exit':0,
        'draft_mock':True,'external_requests':capture['external_requests'],'shots':capture['shots'],'audio':'none; burned-in captions',
        'duration_method':'final timestamp from complete FFmpeg decode',
        'capture_timing_method':capture.get('timing_method','monotonic scene checkpoints')},indent=2)+'\n')
    print('DRAFT/MOCK video:',duration,'seconds; decode exit 0; zero external page requests')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--ffmpeg', help='Path to FFmpeg with libx264; defaults to optional imageio-ffmpeg, then system ffmpeg')
    ap.add_argument('--render-only', action='store_true', help='Resume encoding a completed capture')
    args=ap.parse_args()
    if not args.ffmpeg:
        try:
            import imageio_ffmpeg
            args.ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            args.ffmpeg='ffmpeg'
    if args.render_only:
        render(args.output,args.ffmpeg)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    frames=args.output/'frames'; frames.mkdir()
    clips=args.output/'raw'; clips.mkdir()
    checkpoints=[]; external=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, chromium_sandbox=True,
            args=['--disable-dev-shm-usage','--disable-background-networking'])
        context=browser.new_context(viewport={'width':1280,'height':720}, reduced_motion='reduce',
            record_video_dir=str(clips), record_video_size={'width':1280,'height':720})
        page=context.new_page()
        recording_started=time.monotonic()
        page.on('request', lambda r: external.append(r.url) if r.url.startswith(('http:','https:')) else None)
        video=page.video
        def overlay(caption):
            page.evaluate('''([style,text])=>{for(const id of ['draft-mark','caption','movie-style'])document.getElementById(id)?.remove();const s=document.createElement('style');s.id='movie-style';s.textContent=style;document.head.append(s);const a=document.createElement('div');a.id='draft-mark';a.textContent='DRAFT / MOCK · synthetic rehearsal · no vendor inference';const b=document.createElement('div');b.id='caption';b.textContent=text;document.body.append(a,b);}''',[STYLE[STYLE.index('#draft-mark'):],caption])
        def card(title, body, caption):
            page.evaluate("""([style,title,body])=>{
                document.getElementById('movie-card')?.remove();
                document.getElementById('movie-card-style')?.remove();
                const s=document.createElement('style');s.id='movie-card-style';s.textContent=style;document.head.append(s);
                const cover=document.createElement('div');cover.id='movie-card';cover.style='position:fixed;inset:0;z-index:9000;background:#0c1417';
                const main=document.createElement('div');main.className='card';
                const h=document.createElement('h1');h.textContent=title;
                const p=document.createElement('p');p.textContent=body;
                main.append(h,p);cover.append(main);document.body.append(cover);
            }""", [STYLE,title,body])
            overlay(caption)
        def load():
            page.evaluate("document.getElementById('movie-card')?.remove();document.getElementById('movie-card-style')?.remove()")
        def hold(index, end):
            page.screenshot(path=str(frames/f'{index:02d}.png'))
            checkpoints.append({'shot':index,'captured_seconds':round(time.monotonic()-started,2)})
            page.wait_for_timeout(max(0, end-(time.monotonic()-started))*1000)
        page.goto((ENTRY/'site/index.html').as_uri(), wait_until='domcontentloaded', timeout=60000)
        page.locator('#tour-start').wait_for(state='visible')
        card('SignalDesk','Evidence before action. An inspectable incident brief for tape-library operators.',
             'A cited hypothesis when evidence supports it. A human handoff when it does not.')
        started=time.monotonic()
        hold(1,12)
        load(); page.locator('#tour-start').evaluate('e=>e.click()'); page.locator('#tour-pause').evaluate('e=>e.click()')
        overlay('This is a local MOCK. The live path requests NVIDIA Nemotron on Nebius Token Factory; genuine use is pending.')
        hold(2,42)
        page.locator('#tour-stop').evaluate('e=>e.click()'); page.locator('#case').select_option('H05')
        overlay('Python checks cited observations and exact runbook steps. A threshold supports a hypothesis, not a proven root cause.')
        page.locator('#decision').scroll_into_view_if_needed(); page.evaluate("window.scrollBy(0,-40)")
        page.wait_for_timeout(9000)
        page.locator('#source-link').evaluate('e=>e.click()'); page.evaluate('window.scrollBy(0,-45)')
        hold(3,68)
        page.locator('#case').select_option('H35'); page.locator('#decision').scroll_into_view_if_needed(); page.evaluate('window.scrollBy(0,-45)')
        overlay('Conflicting evidence produces a human handoff and zero proposed steps. No remediation is executed.')
        page.wait_for_timeout(8000)
        page.locator('#case').select_option('H36'); page.locator('#decision').scroll_into_view_if_needed()
        overlay('Missing telemetry also means pause. The assistant cannot invent the observation needed to support a claim.')
        hold(4,90)
        page.locator('#case').select_option('H05'); page.locator('#model').select_option('nvidia/nemotron-3-super-120b-a12b')
        page.locator('summary').evaluate('e=>e.click()'); page.locator('#metrics').scroll_into_view_if_needed(); page.evaluate('window.scrollBy(0,100)')
        overlay('Two requested models, forty frozen cases each. These MOCK counts test plumbing; they are not NVIDIA accuracy or latency.')
        hold(5,115)
        page.set_viewport_size({'width':390,'height':844}); page.evaluate("document.getElementById('caption').remove();document.getElementById('draft-mark').remove()")
        page.locator('#decision').scroll_into_view_if_needed()
        phone=page.screenshot(); page.set_viewport_size({'width':1280,'height':720})
        card('Replay without a key','Every selection uses a saved record. Download evidence; inspect sources. Current requests and cost: zero.',
             'Actual 390px browser viewport capture. Mobile replay remains free of accounts, secrets and inference calls.')
        page.locator('.card').evaluate("e=>{e.style.padding='120px 50px';e.style.width='800px'}")
        page.locator('#movie-card h1').evaluate("e=>e.style.fontSize='48px'")
        page.evaluate("src=>{const i=document.createElement('img');i.src=src;i.alt='Actual mock replay at phone width';i.style='position:absolute;right:35px;top:45px;width:255px';document.getElementById('movie-card').append(i)}",'data:image/png;base64,'+base64.b64encode(phone).decode())
        hold(6,134)
        card('Draft → validate → replay','NVIDIA Nemotron / Nebius Token Factory → independent Python evidence checks → sanitized record → judge replay.',
             'The architecture separates model drafting from source validation. Genuine runtime evidence must replace this MOCK before submission.')
        hold(7,152)
        card('The operator decides.','A cited hypothesis. An honest pause. Evidence for both. Next: independent scenarios and an operator study.',
             'DRAFT / MOCK — owner must add genuine runtime footage and firsthand feedback. No production accuracy or time-saving claim.')
        hold(8,165)
        context.close(); source=Path(video.path()); browser.close()
    assert external == [], external
    (args.output/'capture-results.json').write_text(json.dumps({'draft_mock':True,'external_requests':external,'shots':checkpoints,'lead_in_seconds':round(started-recording_started,3)},indent=2)+'\n')
    render(args.output,args.ffmpeg)

if __name__=='__main__': main()
