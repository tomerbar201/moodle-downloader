import sys
from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)
from qt_material import build_stylesheet, apply_stylesheet
stylesheet = build_stylesheet(theme='dark_teal.xml')

# See if it contains icon:/
print('Contains icon:/ =', 'url(icon:/' in stylesheet)

# Replace it
stylesheet = stylesheet.replace('url(icon:/', 'url(icon:')

print('After replace contains url(icon:/ =', 'url(icon:/' in stylesheet)
