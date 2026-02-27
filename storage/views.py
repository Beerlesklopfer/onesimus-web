"""Views for storage app."""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def storage_view(request):
    """Display storage pools and volumes."""
    context = {
        'title': 'Storage',
    }
    return render(request, 'storage/list.html', context)
