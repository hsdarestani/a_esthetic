from mobile_staff_preview import validate_public_origins as validate

assert validate(None,None)==('http://127.0.0.1:5181','http://127.0.0.1:5182',False)
assert validate('https://preview.example.test','https://preview-book.example.test') == (
    'https://preview.example.test','https://preview-book.example.test',True)
for invalid in [
    ('https://app.a-esthetic.de','https://preview-book.example.test'),
    ('https://preview.example.test','http://preview-book.example.test'),
    ('https://preview.example.test','https://preview.example.test'),
    ('https://preview.example.test/path','https://preview-book.example.test'),
    ('https://preview.example.test',None),
]:
    try:
        validate(*invalid)
    except ValueError:
        continue
    raise AssertionError(invalid)
print('PASS: remote staging rejects production and malformed origins')
