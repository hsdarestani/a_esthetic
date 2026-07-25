from .models import FeatureModule
def feature_modules(request):
    try:
        modules={m.key:m for m in FeatureModule.objects.all()}
    except Exception:
        modules={}
    return {'feature_modules':modules}
