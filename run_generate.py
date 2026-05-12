import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
sys.argv = [
    'run_generate.py',
    '--supplier', 'atos',
    '--category', 'milo',
    '--xml', r'C:\work\mergado-api\atos_source_feed.xml',
]
from polotovar.generate import main
main()
