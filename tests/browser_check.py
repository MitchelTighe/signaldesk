"""Optional real Chromium acceptance: local files, installed Selenium, no downloads.
Run from entry: python3 tests/browser_check.py
"""
from pathlib import Path
import base64
import json
import os
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

ENTRY = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('SIGNALDESK_BROWSER_OUTPUT', ENTRY / 'docs' / 'screenshots'))
OUT.mkdir(parents=True, exist_ok=True)
checks = []
def check(condition, label):
    if not condition:
        raise AssertionError(label)
    checks.append(label)
    print('PASS', label)

scratch = os.environ.get('SIGNALDESK_BROWSER_SCRATCH', tempfile.gettempdir())
with tempfile.TemporaryDirectory(prefix='browser-', dir=scratch) as profile:
    options = Options()
    options.binary_location = os.environ.get('CHROME_BINARY', '/usr/lib64/chromium-browser/chromium-browser')
    for arg in ['--headless=new','--disable-dev-shm-usage','--no-first-run',
                '--disable-background-networking','--disable-extensions','--disable-sync',
                '--no-proxy-server','--user-data-dir='+profile]:
        options.add_argument(arg)
    options.set_capability('goog:loggingPrefs', {'browser':'ALL','performance':'ALL'})
    with webdriver.Chrome(service=Service(os.environ.get('CHROMEDRIVER','/usr/bin/chromedriver')),options=options) as driver:
        driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
        def size(width,height,mobile=False):
            driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'width':width,'height':height,'deviceScaleFactor':1,'mobile':mobile})
        def choose(case_id):
            Select(driver.find_element(By.ID,'ticket')).select_by_value(case_id)
        def shot(name):
            driver.execute_script('window.scrollTo(0,0)')
            raw=driver.execute_cdp_cmd('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})
            (OUT/name).write_bytes(base64.b64decode(raw['data']))
        size(1440,1100)
        driver.get((ENTRY/'web/index.html').as_uri())
        check(driver.title == 'SignalDesk · Evidence before action','page loads from local file')
        check(len(Select(driver.find_element(By.ID,'ticket')).options)==176,'176 actual Python briefs available')
        check(driver.find_element(By.ID,'hypothesis').text=='Worker queue saturation','first brief is rendered')
        choose('clean-demo')
        check(driver.find_element(By.ID,'hypothesis').text=='Drive requests cleaning','ticket change updates hypothesis')
        check('E-C1' in driver.find_element(By.ID,'rationale').text,'hypothesis cites observed evidence')
        check(len(driver.find_elements(By.CSS_SELECTOR,'#steps li'))==3,'supported brief has three runbook steps')
        driver.find_element(By.ID,'runbook-link').click()
        check(driver.current_url.endswith('#source-panel') and 'RB-CLEAN' in driver.find_element(By.ID,'source-title').text,'citation opens the correct local source')
        shot('desktop-supported.png')
        choose('unknown-demo')
        check(driver.find_element(By.ID,'status').text=='NEEDS HUMAN','unknown ticket visibly abstains')
        check(not driver.find_elements(By.CSS_SELECTOR,'#steps li') and driver.find_element(By.ID,'handoff').is_displayed(),'abstention replaces steps with operator handoff')
        shot('desktop-abstention.png')
        choose('injection-demo')
        check(not driver.find_elements(By.CSS_SELECTOR,'#steps li'),'injection ticket creates no remediation')
        choose('H39')
        check('not numeric' in driver.find_element(By.ID,'evidence-body').text,'invalid telemetry value is clearly labeled')
        choose('H16')
        check(driver.find_element(By.ID,'status').text=='NEEDS HUMAN','known held-out miss remains visible in UI')
        driver.find_element(By.TAG_NAME,'body').click()
        driver.find_element(By.TAG_NAME,'body').send_keys('/')
        check(driver.switch_to.active_element.get_attribute('id')=='search','slash shortcut focuses search')
        driver.switch_to.active_element.send_keys('T-DNS')
        check(len(Select(driver.find_element(By.ID,'ticket')).options)==8,'symptom search filters corpus')
        driver.switch_to.active_element.send_keys(Keys.CONTROL,'a')
        driver.switch_to.active_element.send_keys('no-such-fictional-ticket')
        check(driver.find_element(By.ID,'no-results').is_displayed() and not driver.find_element(By.ID,'brief-panel').is_displayed(),'empty search hides stale brief')
        driver.find_element(By.ID,'search').clear()
        driver.execute_script("document.getElementById('search').dispatchEvent(new Event('input'))")
        Select(driver.find_element(By.ID,'filter')).select_by_value('heldout')
        check(len(Select(driver.find_element(By.ID,'ticket')).options)==40,'held-out collection has 40 tickets')
        selector=driver.find_element(By.ID,'ticket'); selector.send_keys(Keys.HOME); selector.send_keys(Keys.ARROW_DOWN); selector.send_keys(Keys.ENTER)
        check(selector.get_attribute('value')=='H02','native ticket selector works with keyboard arrows')
        driver.find_element(By.ID,'previous').click()
        check(selector.get_attribute('value')=='H01','previous ticket control works')
        driver.find_element(By.ID,'next').click()
        check(selector.get_attribute('value')=='H02','next ticket control works')
        Select(driver.find_element(By.ID,'filter')).select_by_value('all'); choose('clean-demo')
        for width in [768,390,320]:
            size(width,844,width<700)
            overflow=driver.execute_script('return document.documentElement.scrollWidth>innerWidth')
            check(not overflow,f'no horizontal overflow at {width}px')
            if width==390:
                check(driver.find_element(By.ID,'ticket').size['height']>=44,'phone selector has 44px touch target')
                shot('phone-supported.png')
                choose('unknown-demo'); shot('phone-abstention.png'); choose('clean-demo')
        size(1440,1100)
        driver.find_element(By.CSS_SELECTOR,'a[href="#evaluation"]').send_keys(Keys.ENTER)
        check(driver.find_element(By.CSS_SELECTOR,'#evaluation details').get_attribute('open') is not None,'evaluation link opens the limits panel')
        check(driver.find_element(By.ID,'eval-counts').text.startswith('27/27'),'evaluation displays real counts')
        shot('desktop-evaluation.png')
        network=[]
        for row in driver.get_log('performance'):
            msg=json.loads(row['message'])['message']
            if msg['method']=='Network.requestWillBeSent':
                url=msg['params']['request']['url']
                if url.startswith(('http://','https://','ws://','wss://')): network.append(url)
        check(network==[], 'zero external page requests observed')
        errors=[x for x in driver.get_log('browser') if x['level']=='SEVERE']
        check(errors==[], 'zero browser console errors')
        result={'browser':driver.capabilities['browserVersion'],'checks_passed':len(checks),
                'checks':checks,'remote_page_requests':network,'console_errors':errors,
                'surface':'file:// web/index.html; installed sandboxed headless Chromium, Selenium; no installs',
                'screenshots':sorted(p.name for p in OUT.glob('*.png'))}
        (OUT/'browser-results.json').write_text(json.dumps(result,indent=2)+'\n')
        print(f"{len(checks)} browser checks passed; Chromium {result['browser']}; {len(result['screenshots'])} screenshots")
