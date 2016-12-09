import sys
sys.path.insert(0, '/var/www/html/app')
from app import app as application
sys.stdout = sys.stderr
