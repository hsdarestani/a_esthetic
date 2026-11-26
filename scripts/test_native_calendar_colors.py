"""Assert equivalent native calendar event palette and actual Android fixture pixels."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
android = (root/'native/staff/android/NativeStaffV3Calendar.java').read_text()
ios = (root/'native/staff/ios/StaffSimplyBookV3.swift').read_text()
assert 'APPOINTMENT_BLUE=Color.rgb(0,125,166)' in android
assert 'int color=isAppointment?APPOINTMENT_BLUE:AMBER;' in android
assert 'int textColor=isAppointment?Color.WHITE:INK;' in android
assert 'labelWidth,10,false,1,textColor);' in android
assert '11,true,h>=d(39)?2:1,textColor);' in android
assert 'title+" / "+detail' in android and 'title+" / "+detail' in ios
assert 'float h=Math.max(1f,yFor(end)-y);' in android
assert 'let height = max(1, CGFloat(max(1,finish-start)) * hourHeight / 60)' in ios
assert 'canvas.clipRect(left+1,y+1,right-1,y+h-1);' in android
assert '"office"' not in android and 'fire("office")' not in ios
assert 'color=Color.rgb(255,214,133)' in android
assert 'color=Color.rgb(227,171,91)' in android
assert 'appointmentBlue = Color(red: 0.0/255, green: 125.0/255, blue: 166.0/255)' in ios
assert '.foregroundStyle(isAppointment ? Color.white : ink)' in ios
assert '.background(isAppointment ? appointmentBlue : isNote ?' in ios
assert 'green: 214.0/255, blue: 133.0/255' in ios
assert 'red: 227.0/255, green: 171.0/255, blue: 91.0/255' in ios
assert 'fab.setBackground(oval(BLUE))' in android
assert '.background(blue, in: Circle())' in ios
# Source-level sticky-ruler regression guards; actual scrolling still requires UI QA.
assert 'value: proxy.frame(in: .named(timelineVerticalSpace)).minY' in ios
assert 'hourRuler.offset(y: verticalOffset)' in ios
assert 'horizontalOffset' not in ios
assert '.zIndex(1)' in ios and 'transaction.disablesAnimations = true' in ios
assert 'pane.addView(fixedRuler,' in android and 'pane.addView(horizontal,' in android
assert 'ruler.setTranslationY(-y)' in android
assert 'ruler.setTranslationX' not in android and 'blank.setTranslationX' not in android
linear = lambda v: v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
luminance = sum(a*linear(v/255) for a,v in zip((.2126,.7152,.0722),(0,125,166)))
assert 1.05/(luminance+.05) >= 4.5
if len(sys.argv)>1:
    from PIL import Image
    from collections import Counter
    pixels = Counter(Image.open(sys.argv[1]).convert('RGB').getdata())
    for name,color in [('appointment',(0,125,166)),('note',(255,214,133)),('block',(227,171,91))]:
        count=pixels[color]
        assert count>=100, (name,color,count)
        print('RENDERED_PALETTE',name,color,count)
print('PASS calendar palette parity and readable appointment contrast')
