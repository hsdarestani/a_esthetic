"""Install the two native staff renderers into disposable generated Capacitor targets."""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MARKER = '// BEGIN APLUS NATIVE STAFF MODULE'


def ios():
    app = ROOT / 'ios/App/App'
    delegate = app / 'AppDelegate.swift'
    if not delegate.exists():
        return
    source = delegate.read_text()
    source = source.split(MARKER, 1)[0].rstrip()
    native = (ROOT / 'native/staff/ios/NativeStaff.swift').read_text()
    calendar = (ROOT / 'native/staff/ios/NativeCalendarTimeline.swift').read_text()
    v3 = (ROOT / 'native/staff/ios/StaffSimplyBookV3.swift').read_text()
    delegate.write_text(source + '\n\n' + MARKER + '\n' + native + '\n\n' + calendar + '\n\n' + v3)
    storyboard = app / 'Base.lproj/Main.storyboard'
    tree = ET.parse(storyboard)
    views = [el for el in tree.iter('viewController')
             if el.get('customClass') in ('CAPBridgeViewController','StaffBridgeViewController')]
    if len(views) != 1:
        raise RuntimeError('Cannot identify generated Capacitor iOS bridge')
    views[0].set('customClass', 'StaffBridgeViewController')
    views[0].set('customModule', 'App')
    views[0].set('customModuleProvider', 'target')
    tree.write(storyboard, encoding='utf-8', xml_declaration=True)
    # Capacitor's iOS plugin discovery list is read by the native bridge on
    # startup. This app-local plugin must be included as well as registered
    # from StaffBridgeViewController, or the JS proxy is UNIMPLEMENTED on iOS.
    config = app / 'capacitor.config.json'
    if not config.is_file():
        raise RuntimeError('Cannot register NativeStaff: generated iOS capacitor.config.json is missing')
    data = json.loads(config.read_text())
    classes = data.setdefault('packageClassList', [])
    if not isinstance(classes, list):
        raise RuntimeError('Invalid iOS Capacitor package class list')
    if 'NativeStaffPlugin' not in classes:
        classes.append('NativeStaffPlugin')
        config.write_text(json.dumps(data, indent=2) + '\n')
    if (app / 'Base.lproj' / 'Main.storyboard').exists():
        controller = ET.parse(app / 'Base.lproj' / 'Main.storyboard').getroot()
        assert any(v.get('customClass') == 'StaffBridgeViewController'
                   for v in controller.iter('viewController')), 'Native staff bridge class not wired'



def android():
    root = ROOT / 'android/app/src/main/java'
    matches = list(root.rglob('MainActivity.java'))
    if not matches:
        return
    if len(matches) != 1:
        raise RuntimeError('Cannot identify generated Android activity')
    main = matches[0]
    code = main.read_text()
    package = re.search(r'^package ([A-Za-z0-9_.]+);', code, re.M)
    if not package:
        raise RuntimeError('Missing Android package')
    native = (ROOT / 'native/staff/android/NativeStaffPlugin.java').read_text()
    (main.parent / 'NativeStaffPlugin.java').write_text(native.replace('NATIVE_STAFF_PACKAGE', package[1]))
    register = 'registerPlugin(NativeStaffPlugin.class);'
    if register not in code:
        if 'super.onCreate(savedInstanceState);' in code:
            code = code.replace('super.onCreate(savedInstanceState);', register+'\n        super.onCreate(savedInstanceState);', 1)
        else:
            pattern = r'(class MainActivity\s+extends BridgeActivity\s*\{)'
            code, count = re.subn(pattern, r'\1'+'\n    @Override public void onCreate(android.os.Bundle savedInstanceState) {\n        '+register+'\n        super.onCreate(savedInstanceState);\n    }\n', code, count=1)
            if count != 1:
                raise RuntimeError('Cannot register native staff plugin')
        main.write_text(code)


if __name__ == '__main__':
    ios()
    android()
