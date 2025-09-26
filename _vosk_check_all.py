from pathlib import Path
import sys, vosk

langs = ['en','hi','fr','de','es']
ok = True
for lg in langs:
    mp = Path(f'vosk_models/{lg}/model').resolve()
    print(f'Loading {lg} from {mp} ...', end=' ', flush=True)
    try:
        vosk.Model(str(mp))
        print('OK ')
    except Exception as e:
        ok = False
        print(f'FAIL   ({e})')

sys.exit(0 if ok else 1)
