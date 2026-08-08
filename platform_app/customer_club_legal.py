from django.shortcuts import render, redirect


def privacy(request):
    """Public privacy page for the A+ Esthetic customer-club app."""
    return render(request, 'customer_club_privacy.html')


def legacy_medical_notice(request):
    """Old route kept only to avoid broken links; it is not part of the product."""
    return redirect('/datenschutz/', permanent=False)
